# Research: Stringing Management

Phase 0 decisions for [plan.md](plan.md). Each entry: Decision, Rationale, Alternatives considered.

## R1. Order number generation (FR-002, SC-002)

**Decision**: A dedicated PostgreSQL sequence `stringing_order_number_seq`, created in a migration.
`create_stringing_order` takes `nextval()` before the insert and formats
`STR-{year}-{n:06d}`, where `year` is the store-local year of creation. The sequence never
resets. `order_number` stays `unique=True`.

**Rationale**:

- `nextval()` is atomic and lock-free, so concurrent creates can never collide.
- Sequence values are never handed out twice, even after a rollback. That gives the spec's "never
  reused" guarantee (a rolled-back create leaves a gap, never a reuse).
- The number is known before the insert, so `order_number` can stay non-null and unique, with no
  placeholder-then-update step.
- The constitution makes PostgreSQL the only supported database, so a Postgres sequence is allowed.

**Alternatives considered**:

- *Derive the number from `pk` after insert* (as sales does, `S{date}-{pk}`): this needs either a
  nullable column or a placeholder value plus a second write. Rejected: the column is already
  non-null and unique, and orders are numbered at creation, not at a later finalize step.
- *A counter row locked with `select_for_update`*: serializes every intake behind one row lock.
  Rejected: slower, no benefit.
- *Random or UUID numbers*: unique, but not readable on a racket tag. Rejected.

## R2. Where payments are recorded and how "paid in full" is tracked (FR-014–017, FR-028)

**Decision**:

- `Payment` (sales app) stays the single record of money. `sales.services.record_payment` /
  `process_refund` stay the single write path.
- A new stringing endpoint `POST /api/stringing/orders/{id}/payments/` calls those services.
- Add `StringingOrder.paid_in_full_at` (nullable, indexed). It is maintained by
  `stringing.services.sync_payment_state(order)`, which:
  - recomputes net paid from posted payments (the shared rule in `sales/selectors.py`);
  - sets `paid_in_full_at` to the time the balance reaches 0.00, or clears it when a balance
    reappears.
- `sales.services.record_payment` calls `sync_payment_state` for stringing targets inside the same
  transaction, while it holds the order lock. It already does the same for `Sale.status`. Because
  of this, payments posted through the generic `/api/sales/payments/` endpoint stay consistent too.
- `update_stringing_order` also calls `sync_payment_state` after a money edit (a discount can make
  an order paid in full; a price increase can reopen a balance).
- Amount paid, balance and payment state are **derived** with `net_paid_subquery("stringing_order")`
  and not stored. One definition of "net paid" stays in use project-wide (customers R3).

**Rationale**:

- The revenue rule (Q1) needs a date for each order, and that date is expensive to derive from
  payment history at query time, so it is stored.
- Storing a cached amount-paid as well would create a second source of truth for money. Rejected.

**Import cycle**: `sales.services` already imports `stringing.models`. It imports
`stringing.services.sync_payment_state` the same way. `stringing.services` imports only
`sales.models` and `sales.selectors` at module level. It imports `sales.services` lazily inside the
payment wrapper, so the module-level graph has no cycle.

**Alternatives considered**:

- *Derive the paid-in-full date with a window function over payments*: correct, but this is a
  per-report window scan over the whole payments table, and it also has to account for later price
  edits. Rejected.
- *A stringing-only payment model*: duplicates the money rules. Rejected by the constitution
  (one write path, append-only Payment).

## R3. Revenue and profit report (FR-026–029, Q1)

**Decision**: `stringing.selectors.revenue_report(date_from, date_to)` interprets the dates in the
store time zone (new setting `STORE_TIME_ZONE = "Asia/Manila"`; storage stays UTC). It returns:

- **Recognized** (non-cancelled orders with `paid_in_full_at` in range):
  - `orders_count`
  - `gross_service_price` = Σ price
  - `total_discounts` = Σ discount
  - `net_revenue` = Σ (price − discount)
  - `total_direct_cost` = Σ cost
  - `profit` = net_revenue − total_direct_cost
- **Cancelled**: `cancelled_count`, orders with `cancelled_at` in range.
- **Not yet paid in full**: `unpaid_count` and `outstanding_balance` over non-cancelled orders
  received in range with `paid_in_full_at IS NULL`.
- **Refunds after pickup**: `total_refunds` = posted refunds on COMPLETED orders with
  `payment_date` in range and on or after the order's `completed_at`. Also
  `net_revenue_after_refunds` and `profit_after_refunds`. `sync_payment_state` never clears
  `paid_in_full_at` on a COMPLETED order, so such refunds don't move revenue between periods.
  A **settled** order (COMPLETED with `paid_in_full_at` set, `StringingOrder.is_settled`) shows
  balance 0.00 and payment state PAID, refuses further receipts, and is excluded from the customer
  summary's outstanding balance. Legacy COMPLETED orders never paid in full are not settled and
  keep their real balance until collected. The `payment_state` filter never matches cancelled
  orders.

The report runs in 3 aggregate queries and needs no pagination.

**Rationale**:

- Implements the clarified rule: an order counts once it is paid in full, on that date.
- Profit uses only the order's own direct cost, matching the spec.

## R4. Status transitions and audit trail (FR-010–013, FR-021–025)

**Decision**:

- A transition table in `stringing/services.py`:
  - RECEIVED → IN_PROGRESS
  - IN_PROGRESS → READY | RECEIVED
  - READY → COMPLETED | IN_PROGRESS
  - COMPLETED and CANCELLED are final.
- `change_status(order_id, to_status, user)` locks the row, checks the table, and refuses
  COMPLETED while the balance is above 0. It sets `ready_at` and `completed_at` and writes a
  `StringingOrderEvent`.
- Cancellation is its own service, `cancel_stringing_order`, never a plain status change.
- **New append-only `StringingOrderEvent`** (FK `PROTECT`). Event types: CREATED, UPDATED,
  STATUS_CHANGED, CANCELLED. It stores `changes` as JSON (`{field: [old, new]}`, money as strings),
  `from_status`, `to_status`, `reason`, `performed_by`, `created_at`.
- **The audit history endpoint** (FR-025) merges events and payments, ordered by time. Payments are
  not copied into events, because they are already append-only records.
- **Stale status changes**: the client may send `expected_status`. If it is sent and does not match
  the current status, the request is refused with the current status ("Concurrent status changes"
  edge case). The row lock prevents lost updates either way.

**Alternatives considered**: django-simple-history or another generic audit package. Rejected: a new
dependency, and it audits every field without the reason and transition meaning.

## R5. Cancellation with money received (FR-021–023, Q3)

**Decision**: follow `cancel_sale`. Lock the row, require a non-blank reason, refuse COMPLETED or
CANCELLED orders, then set status, `cancelled_at`, `cancelled_by` and `cancellation_reason`, and
write a CANCELLED event. Payments are untouched. `refund_due` = net paid when cancelled. Refunds
stay allowed through `record_payment` (it already refuses only *receipts* on cancelled stringing
orders).

## R6. Permissions (FR-030)

**Decision**: fix `StringingOrder.Meta.permissions`. It is currently declared outside `Meta`, so
Django ignores it. Declare:

- `stringing.cancel_stringingorder`: cancel orders.
- `stringing.view_stringing_financials`: see direct cost, per-order profit, and the revenue report.

Payments reuse `sales.record_payment` (receipts) and `sales.process_refund` (refunds).

The unused `manage_stringing_orders` permission is dropped. It was never created, because it was
outside `Meta`.

**Direct cost without the financials permission**: the field can be **written** at intake (counter
staff know which string was used), but it is omitted from every response. An **edit** that changes
`direct_cost` without the permission is refused with 403, so the value cannot be probed by
trial edits.

**Related gap (flagged)**: the existing generic `POST /api/sales/payments/` checks only the refund
permission, not `sales.record_payment` for receipts. Any signed-in user could therefore record a
stringing receipt there and bypass FR-030. This plan adds the `record_payment` check for receipts on
that endpoint. This is a small behaviour change for sales; the existing sales API tests must be
updated to grant the permission.

## R7. Search and filtering (FR-018–020, SC-003)

**Decision**:

- `stringing.selectors.search_orders(params)`:
  - `search`: case-insensitive `icontains` on `order_number`, `racket_description`, `string_type`
    and `customer__full_name`. If the text looks like a phone number (`customers.phone.is_phone_query`),
    it also matches `customer__phone_normalized` (contains `normalize_phone(q)`).
  - `status`: comma-separated list.
  - `payment_state`: `unpaid` | `partial` | `paid`, using the net-paid annotation compared with the
    total.
  - `customer`: id.
  - `received_from` / `received_to`: store-local dates.
  - `ordering`: `-created_at` (default) | `created_at` | `status`.
- Indexes: `(status, -created_at)`, `created_at`, `paid_in_full_at` (the customer FK index already
  exists).

**Rationale**: 50k rows with `icontains` and an indexed status/date filter stay well within 300 ms on
Postgres. No `pg_trgm` is needed (same reasoning as customers R2).

## R8. Data migration for existing rows

**Decision**: a data migration does three things for existing orders:

- Sets `paid_in_full_at` for orders whose net paid equals their total. It uses the latest posted
  payment date, or `created_at` for zero-total orders.
- Sets `updated_at` to `created_at`.
- Writes nothing to the event table, because history before this feature is unknown.

Existing `order_number` values are kept. The sequence starts above the highest numeric suffix found
among existing `STR-` numbers.

## R9. Frontend scope

**Decision**: backend only, as in customers R10. The screen states in the spec are supported by the
contract: empty lists, field-keyed errors, and confirmation payloads. They are built in a later
frontend feature.
