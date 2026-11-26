# Data Model: Stringing Management

## StringingOrder (existing, extended) — `stringing.models`

| Field | Type | Notes |
|---|---|---|
| `order_number` | Char(30), unique | `STR-{year}-{seq:06d}` from `stringing_order_number_seq` (R1). Not editable. |
| `customer` | FK Customer, null, `PROTECT` | Optional (walk-in). Must be active when set or changed (`customers.services.ensure_usable`). |
| `racket_description` | Char(150) | Required, not blank (stripped). |
| `string_type` | Char(150) | Required, not blank (stripped). |
| `tension` | Char(50), blank | Free text as entered. |
| `notes` | Text, blank | **New.** |
| `service_price` | Decimal(10,2) | ≥ 0. |
| `discount_amount` | Decimal(10,2), default 0 | 0 ≤ discount ≤ price. |
| `direct_cost` | Decimal(10,2), default 0 | ≥ 0. Hidden without `view_stringing_financials`. |
| `status` | TextChoices | RECEIVED (default), IN_PROGRESS, READY, COMPLETED, CANCELLED. |
| `created_by` / `created_at` | FK User `PROTECT` / DateTime | Existing. |
| `updated_at` | DateTime, auto_now | **New.** |
| `ready_at` | DateTime, null | **New.** Set on entering READY; cleared on stepping back to IN_PROGRESS. |
| `completed_at` | DateTime, null | Existing. Set on COMPLETED. |
| `paid_in_full_at` | DateTime, null, indexed | **New.** Revenue recognition date (R2/R3). |
| `cancelled_at` | DateTime, null | **New.** |
| `cancelled_by` | FK User, null, `PROTECT` | **New.** |
| `cancellation_reason` | Text, blank | Existing. |

**Derived (annotations / properties, not stored)**:

- `total_amount` = price − discount.
- `amount_paid` = net paid (posted receipts − refunds).
- `is_settled` = COMPLETED and `paid_in_full_at` set.
- `balance` = total − amount_paid. Shown as 0 for cancelled and settled orders (a refund after
  pickup does not reopen a balance).
- `refund_due` = amount_paid for cancelled orders, otherwise 0.
- `payment_state` (always `PAID` for settled orders): `UNPAID` (paid = 0 and total > 0) | `PARTIAL` (0 < paid < total) |
  `PAID` (paid ≥ total).
- `profit` = total − direct_cost.

**Constraints (DB)**:

- Existing: price ≥ 0, discount ≥ 0, cost ≥ 0, discount ≤ price.
- New: `stringing_racket_not_blank` and `stringing_string_type_not_blank` (trimmed length > 0).
- New: `stringing_cancel_fields_consistent`. The status is CANCELLED ⇔ `cancelled_at` is set
  and the reason is not blank.
- New: `stringing_completed_has_time`. COMPLETED ⇒ `completed_at` is set.

**Indexes**: `(status, -created_at)`, `(-created_at)`, `(paid_in_full_at)`.

**Meta.permissions**: `cancel_stringingorder`, `view_stringing_financials` (R6).

### State transitions

```text
RECEIVED ⇄ IN_PROGRESS ⇄ READY ──(balance = 0)──▶ COMPLETED
    │            │          │
    └────────────┴──────────┴──cancel(reason)──▶ CANCELLED
```

- Forward moves go one step at a time. A move back is allowed one step at a time, and never from
  COMPLETED.
- COMPLETED and CANCELLED are final. No edits, status changes or receipts. Refunds are still
  allowed on both.
- Edits to fields are allowed only in RECEIVED, IN_PROGRESS and READY.

## StringingOrderEvent (new) — append-only audit

| Field | Type | Notes |
|---|---|---|
| `order` | FK StringingOrder, `PROTECT`, related `events` | |
| `event_type` | TextChoices | CREATED, UPDATED, STATUS_CHANGED, CANCELLED |
| `from_status` / `to_status` | Char, blank | For STATUS_CHANGED and CANCELLED. |
| `changes` | JSON, default `{}` | UPDATED: `{field: [old, new]}`. Money values are strings. `direct_cost` changes are included but masked in responses without the financials permission. |
| `reason` | Text, blank | CANCELLED. |
| `performed_by` | FK User, `PROTECT` | |
| `created_at` | DateTime, auto_now_add | |

Index `(order, created_at)`. There are no update or delete paths in services; the admin is
read-only.

## Payment (existing, sales app) — unchanged schema

Linked through `stringing_order`. Receipts are refused on CANCELLED orders and can't exceed the
balance. Refunds can't exceed net paid. Those rules are already in `record_payment`. New in this
feature: `record_payment` calls `stringing.services.sync_payment_state` for stringing targets.

## Validation summary (spec → rule)

| Spec | Rule | Enforced in |
|---|---|---|
| FR-001/004 | Racket and string not blank; amounts valid | serializer + service + DB constraints |
| FR-002 | Unique number, never reused | sequence + unique constraint |
| FR-003 | Customer must be active on create/change | `ensure_usable` in service |
| FR-007 | Edits only before COMPLETED/CANCELLED | service |
| FR-008 | New total ≥ net paid | service (under row lock) |
| FR-011 | Allowed transitions only | service transition table |
| FR-013 | COMPLETED needs balance = 0 | service (under row lock) |
| FR-015 | Receipt ≤ balance | `sales.services.record_payment` |
| FR-017 | Refund needs reason + permission, ≤ net paid | `process_refund` + view permission check |
| FR-021/022 | Cancel needs a reason, a permission, and a non-final state | service + view + DB constraint |
| FR-024 | No delete | no endpoint; FKs `PROTECT`; admin delete disabled |
| FR-030 | Cost hidden without permission | serializer field-level masking |
