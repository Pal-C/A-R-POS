# Research: Pre-order Management

Phase 0 decisions for [plan.md](plan.md). This feature follows the stringing feature
([002 research](../002-stringing-management/research.md)) wherever the problem is the same; only
differences are argued in full here.

## R1. Order numbers (FR-002)

**Decision**: a PostgreSQL sequence, `preorder_number_seq`, formats numbers as `PO-{year}-{n:06d}`
(year in `STORE_TIME_ZONE`). It is created by a migration and starts above the highest numeric
suffix of any existing `PO-` number. This is the same approach as stringing R1.

## R2. Payments, balance and settled orders (FR-012–015, FR-016)

**Decision**:

- **Payments**: money stays in the shared `Payment` table and goes through
  `sales.services.record_payment` / `process_refund`. A pre-order wrapper,
  `preorders.services.record_preorder_payment`, delegates to them, as stringing R2 does.
- **Derived values**: amount paid, balance and payment state are derived with
  `net_paid_subquery("preorder")`.
- **Settled date**: `settled_at` is stored, set when the order is fulfilled (fulfillment requires full
  payment). There is no revenue report in scope, so no `paid_in_full_at` is needed.
- **Legacy fulfilled orders**: pre-orders fulfilled before this feature without full payment are
  not settled. They keep their real balance and still accept receipts. When their balance reaches
  0.00, `sales.services.record_payment` calls `preorders.services.sync_settlement`, which sets
  `settled_at`.
- **Settled orders**: a FULFILLED pre-order with `settled_at` set is settled. It shows balance 0.00 and state PAID, and
  refuses new receipts.
  - `record_payment` today refuses receipts only on CANCELLED pre-orders, so this adds a FULFILLED
    check.
  - Refunds stay allowed, for after-sale corrections.
- **Customer summary**: FULFILLED pre-orders leave both "owed" and "paid" in the customer summary,
  matching the settled stringing rule. Without this, a refund after fulfillment would show as money
  owed.

**Rationale**: consistent with the stringing decisions the user approved (full payment before
handover; a refund after handover does not reopen a balance).

## R3. No inventory interaction (FR-017, Q1)

**Decision**: no pre-order service calls `inventory.services`. Leftover units from an arrival are
only reported; staff restock them through the existing inventory endpoint if they want them on the
shelf.

**Rationale**: the user chose "pre-orders never touch stock".

## R4. Status workflow, arrival and fulfillment (FR-007–011, FR-016)

**Decision**:

- **Transitions**:
  - PENDING → ORDERED
  - ORDERED → ARRIVED | PENDING
  - ARRIVED → ORDERED
  - FULFILLED and CANCELLED are final.
- **`change_status(order_id, user, to_status, expected_status=None)`** handles single-order moves.
  - It sets `ordered_at` and `arrived_at`, and clears them on a step back.
  - It refuses FULFILLED (use `fulfill_preorder`, which has the balance check) and CANCELLED (use
    `cancel_preorder`, which requires a reason).
  - A stale `expected_status` raises `StatusConflict`, as in stringing.
- **`mark_product_arrived(product_id, received_quantity, user, preorder_ids=None)`** handles a
  delivery (Q3).
  - It locks that product's ORDERED pre-orders with `select_for_update`, in primary-key order to
    avoid deadlocks, inside one transaction.
  - **Default** (`preorder_ids` omitted): it walks the orders oldest first (`created_at`, `id`) and
    marks each whose full quantity fits in the remaining units. Orders that don't fit are skipped,
    so a smaller newer order can still be served.
  - **Selected** (`preorder_ids` given): every id must be an ORDERED pre-order of this product, and
    the quantities together must not exceed `received_quantity`. Otherwise nothing is changed and
    the error names the problem.
  - Each marked order gets `arrived_at` and a STATUS_CHANGED event carrying
    `{"arrival": {"received_quantity": n}}`.
  - It returns `{marked: [orders], units_used, units_left}`. If there are no ORDERED pre-orders,
    it returns an empty `marked` list and the full quantity as `units_left`; this is not an error.
- **`fulfill_preorder(order_id, user)`** requires ARRIVED and a balance of 0.00. It sets
  `fulfilled_at` and `fulfilled_by` and writes a STATUS_CHANGED event.

## R5. Editing and the price-override permission (FR-005, FR-026)

**Decision**:

- **Editable fields and when**:
  - `quantity`, `agreed_unit_price`, `expected_arrival_date` and `notes` while PENDING or ORDERED;
  - only `expected_arrival_date` and `notes` while ARRIVED;
  - nothing once FULFILLED or CANCELLED.
- **Checks on an edit**:
  - The new total must not be below net paid.
  - Changing `agreed_unit_price` when net paid is above 0 requires
    `preorders.override_preorder_price`. The view passes `can_override_price` to the service, and
    the service refuses the change with a permission error.
  - A changed `expected_arrival_date` must be today or later in store-local time. An unchanged past
    date is accepted, so an overdue order can still get its notes edited.
- **Audit**: edits write an UPDATED event `{field: [old, new]}`.

## R6. Audit trail (FR-025)

**Decision**: a new append-only `PreOrderEvent` with the same shape as `StringingOrderEvent`.
- Event types: CREATED, UPDATED, STATUS_CHANGED and CANCELLED.
- Fulfillment is a STATUS_CHANGED to FULFILLED.
- An `extra` JSON field holds arrival-batch details.
- The history endpoint merges events and payments, ordered by time, using `payment_date` for
  payments.

**Alternatives considered**: a shared generic event table across apps. Rejected for now: it would
mean migrating the stringing data and introducing generic foreign keys, which is more change than
this feature needs. The duplication is small (one model, one helper) and is noted in Complexity
Tracking.

## R7. Permissions (FR-026)

**Decision**: fix `PreOrder.Meta.permissions`. It is currently declared outside `Meta`, so Django
ignores it, which is the same bug stringing had. Declare:

- `preorders.cancel_preorder`: cancel a pre-order.
- `preorders.override_preorder_price`: change the agreed price after a payment.

Payments use `sales.record_payment` (already granted to existing users by `sales.0005`) and
`sales.process_refund`. The unused `manage_preorders` permission is dropped; it was never created.

## R8. Search, filters, overdue and the per-product summary (FR-011, FR-018–021)

**Decision**:

- **`search_preorders(params)`**:
  - **search**: `icontains` on `order_number`, `customer__full_name`, `product__name` and
    `product__sku`. Phone-like text also matches `customer__phone_normalized`.
  - **filters**:
    - `status`: comma list;
    - `payment_state`: cancelled orders never match;
    - `customer` and `product`: ids;
    - `expected_from` / `expected_to`: dates;
    - `overdue=true`.
  - **ordering**: `-created_at` (default), `created_at` or `expected_arrival_date`. Nulls go last.
- **Overdue**: annotated as `is_overdue`, which is true when `expected_arrival_date` is before the
  store-local today and the status is PENDING or ORDERED.
- **`product_preorder_summary(product)`** returns:
  - the order count and unit total for each of PENDING, ORDERED and ARRIVED;
  - the ORDERED pre-orders, oldest first, for staff to pick from (Q3 option B).
  It takes 2 queries.
- **Indexes**: `(status, -created_at)`, `(product, status)`, `expected_arrival_date` and
  `-created_at`.

## R9. Data migration for existing rows

**Decision**: a backfill runs before the new constraints are added:

- `updated_at` = `created_at`.
- FULFILLED rows without `fulfilled_at` get `created_at`, and get `fulfilled_by` = `created_by`.
- `fulfilled_at` is cleared on rows that aren't FULFILLED. The old model allowed it on any status,
  and the new constraint doesn't.
- `settled_at` is set only on FULFILLED rows whose posted payments cover the total.
- CANCELLED rows get `cancelled_at`/`cancelled_by` from `created_at`/`created_by`, plus a
  placeholder reason.
- ORDERED and ARRIVED rows are left without `ordered_at` or `arrived_at`. Those fields are nullable,
  and the history before this feature is unknown.

## R10. Frontend scope

**Decision**: backend only, as in features 001 and 002.
