---

description: "Task list for Pre-order Management (003)"
---

# Tasks: Pre-order Management

**Input**: Design documents from `/specs/003-preorder-management/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/preorders-api.md](contracts/preorders-api.md),
[quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle II (non-negotiable) requires service, API, constraint,
concurrency and query-count tests. Within each story, write tests first.

**Organization**: tasks are grouped by user story (spec.md US1–US6).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6
- Paths are relative to the repository root

## Path Conventions

Web application: Django backend in `backend/`. No frontend changes ([R10](research.md#r10-frontend-scope)).

---

## Phase 1: Setup

- [X] T001 [P] Create `backend/preorders/services.py`, `backend/preorders/selectors.py`,
  `backend/preorders/serializers.py`, `backend/preorders/urls.py` (empty `urlpatterns`) and the
  `backend/preorders/tests/__init__.py` package. Replace the placeholder `backend/preorders/views.py`
  with an empty module.
- [X] T002 Mount `path("api/preorders/", include("preorders.urls"))` in `backend/config/urls.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: no user story work can begin until this phase is complete.

- [X] T003 Extend `PreOrder` in `backend/preorders/models.py`:
  - Add the new fields from data-model.md: `PreOrder.notes`, `PreOrder.updated_at`,
    `PreOrder.ordered_at`, `PreOrder.arrived_at`, `PreOrder.fulfilled_by`, `PreOrder.cancelled_at`,
    `PreOrder.cancelled_by` and `PreOrder.cancellation_reason`.
  - Add `FINAL_STATUSES`, the `total_amount` docstring, and an `is_settled` property (FULFILLED).
  - Add the indexes from data-model.md.
  - Move the permissions inside `Meta` as `cancel_preorder` and `override_preorder_price`
    ([R7](research.md#r7-permissions-fr-026)).
  - Leave the new constraints out for now (they come in T008).
- [X] T004 Add the `PreOrderEvent` model to `backend/preorders/models.py`:
  - fields from data-model.md: `PreOrderEvent.preorder`, `PreOrderEvent.event_type`,
    `PreOrderEvent.from_status`, `PreOrderEvent.to_status`, `PreOrderEvent.changes`,
    `PreOrderEvent.extra`, `PreOrderEvent.reason`, `PreOrderEvent.performed_by` and
    `PreOrderEvent.created_at`;
  - the `(preorder, created_at)` index.
- [X] T005 Generate `backend/preorders/migrations/0002_preorder_management.py` (schema only, no
  constraints) and review it.
- [X] T006 Write `backend/preorders/migrations/0003_order_number_seq.py`:
  - `RunSQL` creates `preorder_number_seq`, starting above the highest numeric suffix of existing
    `PO-` numbers;
  - reverse drops the sequence ([R1](research.md#r1-order-numbers-fr-002)).
- [X] T007 Write data migration `backend/preorders/migrations/0004_backfill.py` per
  [R9](research.md#r9-data-migration-for-existing-rows) (no-op reverse). It fills
  `PreOrder.updated_at`, `PreOrder.fulfilled_at`, `PreOrder.fulfilled_by`, `PreOrder.cancelled_at`,
  `PreOrder.cancelled_by` and `PreOrder.cancellation_reason` for legacy rows.
- [X] T008 Add `preorder_cancel_fields_consistent` and `preorder_fulfilled_fields_consistent` to
  `PreOrder.Meta` in `backend/preorders/models.py`. They check data-model.md `PreOrder.status`
  together with the cancel and fulfill fields. Write
  `backend/preorders/migrations/0005_preorder_constraints.py`. Then confirm migrate,
  `makemigrations --check`, and reverse-then-reapply all work.
- [X] T009 [P] Create `backend/preorders/tests/factories.py`:
  - `make_user(perms=...)`, `make_customer`, `make_product`, `make_preorder(**overrides)` (through
    the service) and `make_payment(preorder, amount, type)`;
  - update `make_preorder` in `backend/customers/tests/factories.py` to delegate to it, keeping its
    signature and supporting a `status` override for history tests.
- [X] T010 [P] Write constraint and permission tests in `backend/preorders/tests/test_models.py`.
- [X] T011 Add to `backend/preorders/selectors.py`:
  - `annotate_payment_state(queryset)`, which annotates `order_total`, `amount_paid`,
    `payment_state` (FULFILLED → PAID) and `is_overdue`;
  - `preorder_queryset()`, using `select_related` for customer, product, created_by, fulfilled_by
    and cancelled_by;
  - `store_today()`.
- [X] T012 Add the service helpers to `backend/preorders/services.py`:
  - `_next_order_number`, `_lock_preorder`, `_net_paid` and `_record_event`;
  - the `StatusConflict` exception.
- [X] T013 Add `PreOrderListSerializer` and `PreOrderDetailSerializer` to
  `backend/preorders/serializers.py`, per the contract representation, plus the customer, product
  and user reference serializers. Add `run_service` and `detail_response` helpers to
  `backend/preorders/views.py`.

**Checkpoint**: migrations apply; `manage.py test preorders customers sales` passes.

---

## Phase 3: User Story 1 - Take a pre-order with a deposit (Priority: P1) 🎯 MVP

**Goal**: create, view and edit pre-orders with unique numbers.

**Independent Test**: create a pre-order (quantity 2, price 5,000.00). It gets a `PO-YYYY-NNNNNN`
number, status PENDING and total 10,000.00. An archived customer, an inactive product or a past
date is refused.

### Tests for User Story 1

- [X] T014 [P] [US1] Write service tests in `backend/preorders/tests/test_services.py`.
  - `create_preorder`:
    - success;
    - the price defaults to the product's selling price;
    - the number format increments;
    - each field rejection (quantity, price, past date);
    - an archived customer or inactive product is refused;
    - a CREATED event is written.
  - `update_preorder`:
    - editable fields by status;
    - a total below the amount paid is refused;
    - a price change after payment is refused without `can_override_price` and allowed with it;
    - a changed past date is refused while an unchanged past date is accepted;
    - an UPDATED event records old and new values.
- [X] T015 [P] [US1] Write API tests in `backend/preorders/tests/test_api.py` for POST
  `/api/preorders/`, GET `/{id}/` and PATCH `/{id}/`:
  - shapes, 400s, 404, 405 on DELETE;
  - 403 for a price override without the permission;
  - a query-count assertion on the detail view.
- [X] T016 [P] [US1] Write a concurrency test in `backend/preorders/tests/test_concurrency.py`:
  parallel creates get distinct numbers.

### Implementation for User Story 1

- [X] T017 [US1] Implement `create_preorder(*, user, customer, product, quantity,
  agreed_unit_price=None, expected_arrival_date=None, notes="")` in
  `backend/preorders/services.py`:
  - validate data-model.md `PreOrder.customer`, `PreOrder.product`, `PreOrder.quantity`,
    `PreOrder.agreed_unit_price` and `PreOrder.expected_arrival_date`, with field-keyed errors;
  - assign the number from the sequence;
  - write a CREATED event.
- [X] T018 [US1] Implement `update_preorder(*, preorder_id, user, can_override_price=False,
  **changes)` in `backend/preorders/services.py` per [R5](research.md#r5-editing-and-the-price-override-permission-fr-005-fr-026):
  - lock the row;
  - check which fields can be edited in the current status;
  - require total ≥ amount paid;
  - raise `PermissionDenied` (Django core) for a price override without permission;
  - check the date;
  - write an UPDATED event.
- [X] T019 [US1] Add `PreOrderCreateSerializer` and `PreOrderUpdateSerializer` to
  `backend/preorders/serializers.py`. Add `PreOrderListCreateView` (POST; GET comes in US5) and
  `PreOrderDetailView` (GET/PATCH, mapping the Django `PermissionDenied` to 403) to
  `backend/preorders/views.py`, and route them in `backend/preorders/urls.py`.
- [X] T020 [US1] Make `backend/preorders/admin.py` read-only: no add, change or delete, and a
  read-only events inline. Keep `PreOrderAdminForm` for the customers admin-form tests.

**Checkpoint**: US1 tests pass.

---

## Phase 4: User Story 2 - Record deposits and payments (Priority: P1)

**Goal**: receipts and refunds, with paid, balance and payment state shown.

**Independent Test**: on a 10,000.00 pre-order, a 4,000.00 receipt gives PARTIAL with balance
6,000.00, a 7,000.00 receipt is refused, and a 6,000.00 receipt gives PAID.

### Tests for User Story 2

- [X] T021 [P] [US2] Add payment service tests to `backend/preorders/tests/test_services.py`:
  - partial, then full;
  - over-balance refused;
  - invalid amount or method refused;
  - receipt on a CANCELLED or FULFILLED order refused;
  - refund without a reason refused;
  - refund above the amount paid refused.
- [X] T022 [P] [US2] Add API tests for GET/POST `/api/preorders/{id}/payments/` to
  `backend/preorders/tests/test_api.py`: 201 shape, 403 for receipts and refunds without
  permission, 400 cases, paged GET, 404.
- [X] T023 [P] [US2] Add a concurrency test to `backend/preorders/tests/test_concurrency.py`:
  two parallel receipts never exceed the total.
- [X] T024 [P] [US2] Add a regression test to `backend/sales/tests/test_services.py`: a receipt on a
  FULFILLED pre-order through `record_payment` is refused, and a refund is allowed.

### Implementation for User Story 2

- [X] T025 [US2] In `backend/sales/services.py`, make `record_payment` refuse receipts on FULFILLED
  pre-orders ([R2](research.md#r2-payments-balance-and-settled-orders-fr-012015-fr-016)), and update
  its docstring.
- [X] T026 [US2] Implement `record_preorder_payment(...)` in `backend/preorders/services.py`,
  delegating to the sales services (lazy import) and returning `(payment, preorder)`.
- [X] T027 [US2] Add `PreOrderPaymentCreateSerializer` and `PaymentSerializer` output to
  `backend/preorders/serializers.py`, and `PreOrderPaymentsView` to `backend/preorders/views.py`.
  Route it in `backend/preorders/urls.py`.

**Checkpoint**: US1 + US2 tests pass.

---

## Phase 5: User Story 3 - Track status from order to arrival (Priority: P1)

**Goal**: single status changes, arrival of a product (oldest first or picked orders), and the
per-product waiting summary.

**Independent Test**: two ORDERED pre-orders for one product (quantities 2 and 1). An arrival of 2
units marks only the older one and leaves 0 units. A second arrival choosing the other order marks
it. Product stock is unchanged.

### Tests for User Story 3

- [X] T028 [P] [US3] Add `change_status` tests to `backend/preorders/tests/test_services.py`:
  - each allowed transition and each step back;
  - timestamps set and cleared;
  - FULFILLED, CANCELLED and skipped transitions refused;
  - final states refused;
  - stale `expected_status` refused;
  - STATUS_CHANGED events written.
- [X] T029 [P] [US3] Add `mark_product_arrived` tests to `backend/preorders/tests/test_services.py`:
  - oldest-first ordering;
  - an order that doesn't fit is skipped;
  - leftover units reported;
  - none waiting gives an empty result;
  - selected ids success;
  - a selected id that is not ORDERED, or belongs to another product, refused;
  - selected quantities over the received amount refused, with nothing changed;
  - `received_quantity` < 1 refused;
  - events carry the arrival details;
  - no `InventoryMovement` rows are created and product `stock_quantity` is unchanged.
- [X] T030 [P] [US3] Add a `product_preorder_summary` test to
  `backend/preorders/tests/test_selectors.py`: counts and units per status, ORDERED list oldest
  first, query count of 2.
- [X] T031 [P] [US3] Add API tests to `backend/preorders/tests/test_api.py` for `/status/`,
  `products/{id}/summary/` and `products/{id}/arrivals/`: shapes, 400s, 404s.
- [X] T032 [P] [US3] Add a concurrency test to `backend/preorders/tests/test_concurrency.py`: two
  parallel arrivals of 1 unit, with one ORDERED order of quantity 1. Exactly one of them marks it.

### Implementation for User Story 3

- [X] T033 [US3] Implement `ALLOWED_TRANSITIONS` and `change_status` in
  `backend/preorders/services.py`, maintaining data-model.md `PreOrder.ordered_at` and
  `PreOrder.arrived_at` ([R4](research.md#r4-status-workflow-arrival-and-fulfillment-fr-007011-fr-016)).
- [X] T034 [US3] Implement `mark_product_arrived(*, product_id, received_quantity, user,
  preorder_ids=None)` in `backend/preorders/services.py` (R4).
- [X] T035 [US3] Implement `product_preorder_summary(product)` in `backend/preorders/selectors.py`.
- [X] T036 [US3] Add `StatusChangeSerializer` and `ArrivalSerializer` to
  `backend/preorders/serializers.py`, and `PreOrderStatusView`, `ProductPreorderSummaryView` and
  `ProductArrivalView` to `backend/preorders/views.py`. Route them.

**Checkpoint**: US1–US3 tests pass.

---

## Phase 6: User Story 4 - Fulfill a pre-order (Priority: P1)

**Goal**: hand-over only when the order is ARRIVED and fully paid.

**Independent Test**: an ARRIVED pre-order with a balance is refused, a PENDING one is refused, and
a fully paid ARRIVED one becomes FULFILLED with the user and time recorded and stock unchanged.

### Tests for User Story 4

- [X] T037 [P] [US4] Add `fulfill_preorder` tests to `backend/preorders/tests/test_services.py`:
  - success records `fulfilled_at` and `fulfilled_by` and writes an event;
  - refused when not ARRIVED;
  - refused with a balance, and the message shows the amount;
  - refused when already final;
  - stock unchanged.
- [X] T038 [P] [US4] Add API tests for `/fulfill/` to `backend/preorders/tests/test_api.py`.

### Implementation for User Story 4

- [X] T039 [US4] Implement `fulfill_preorder(*, preorder_id, user)` in
  `backend/preorders/services.py`, setting data-model.md `PreOrder.fulfilled_at` and
  `PreOrder.fulfilled_by`.
- [X] T040 [US4] Add `PreOrderFulfillView` to `backend/preorders/views.py` and route it.

**Checkpoint**: P1 MVP complete (US1–US4).

---

## Phase 7: User Story 5 - Find pre-orders (Priority: P2)

**Goal**: search, filters (including overdue) and ordering, paged.

**Independent Test**: filtering `status=ORDERED&product=X` returns only those pre-orders.
`overdue=true` returns only PENDING or ORDERED orders whose date has passed.

### Tests for User Story 5

- [X] T041 [P] [US5] Write `search_preorders` tests in `backend/preorders/tests/test_selectors.py`:
  - each search field, including phone formats and SKU;
  - multi-status filter;
  - payment state (cancelled excluded);
  - customer and product filters;
  - expected-arrival range;
  - overdue;
  - each ordering, with nulls last;
  - invalid values raise errors.
- [X] T042 [P] [US5] Add list API tests to `backend/preorders/tests/test_api.py`: paging, filters,
  empty result, 400, and a constant query count.

### Implementation for User Story 5

- [X] T043 [US5] Implement `search_preorders(params)` in `backend/preorders/selectors.py`
  ([R8](research.md#r8-search-filters-overdue-and-the-per-product-summary-fr-011-fr-018021)).
- [X] T044 [US5] Add GET to `PreOrderListCreateView` in `backend/preorders/views.py`, with
  `filter_backends = []`.

---

## Phase 8: User Story 6 - Cancel a pre-order (Priority: P2)

**Goal**: cancel with a reason; refund due shown; refunds allowed afterwards; full history.

**Independent Test**: cancel a pre-order with a 4,000.00 deposit. It becomes CANCELLED with the
reason, user and time; `refund_due` is 4,000.00; a receipt is refused; a refund is allowed; the
history shows every step.

### Tests for User Story 6

- [X] T045 [P] [US6] Add `cancel_preorder` tests to `backend/preorders/tests/test_services.py`:
  - success from PENDING, ORDERED and ARRIVED;
  - blank reason refused;
  - final states refused;
  - payments untouched;
  - CANCELLED event written;
  - edits and status changes refused afterwards.
  Add `preorder_history` tests to `backend/preorders/tests/test_selectors.py`: events and payments
  merged by time, with arrival details included.
- [X] T046 [P] [US6] Add API tests to `backend/preorders/tests/test_api.py` for `/cancel/` (200,
  400, 403, 404) and `/history/`.

### Implementation for User Story 6

- [X] T047 [US6] Implement `cancel_preorder(*, preorder_id, user, reason)` in
  `backend/preorders/services.py`, setting data-model.md `PreOrder.status`,
  `PreOrder.cancelled_at`, `PreOrder.cancelled_by` and `PreOrder.cancellation_reason`.
- [X] T048 [US6] Implement `preorder_history(preorder)` in `backend/preorders/selectors.py`.
- [X] T049 [US6] Add `CancelSerializer`, `PreOrderCancelView` (permission
  `preorders.cancel_preorder`) and `PreOrderHistoryView` to `backend/preorders/serializers.py` and
  `backend/preorders/views.py`, and route them.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T050 In `backend/customers/selectors.py`, treat FULFILLED pre-orders as settled in
  `customer_summary`: leave them out of both the amount owed and the amount paid (R2). Extend the
  summary test in `backend/customers/tests/test_selectors.py` with a refund after fulfillment.
- [X] T051 [P] Write an end-to-end workflow test in `backend/preorders/tests/test_workflow.py`,
  following the quickstart walkthrough.
- [X] T052 [P] Write a table-driven 401 test for every endpoint in
  `backend/preorders/tests/test_auth.py`.
- [X] T053 From `backend/`, run the full `python manage.py test`, `ruff check .`, ruff format
  (changed files only) and `makemigrations --check`. Fix any failures.

## Phase 10: Review Follow-ups (2026-11-26)

- [X] T054 Add `PreOrder.settled_at` and the `preorder_settled_only_when_fulfilled` constraint in
  `backend/preorders/models.py`, and in migrations 0002 and 0005 (these hadn't left the branch).
  `fulfill_preorder` sets `settled_at`. `sync_settlement`, called from
  `backend/sales/services.py`, settles legacy fulfilled orders once they are paid in full. Selectors,
  serializers and `backend/customers/selectors.py` use the settled rule.
- [X] T055 Make backfill `backend/preorders/migrations/0004_backfill.py` clear `fulfilled_at` on rows
  that aren't FULFILLED, and settle only fulfilled rows that were paid in full. Covered by tests.
- [X] T056 Make the test factories in `backend/customers/tests/factories.py` keep `order_number`
  overrides instead of dropping them silently.

---

## Dependencies & Execution Order

- Setup → Foundational → US1.
- US2 to US6 each depend on US1 only. US4's tests use factory payments and status changes, so they
  don't need US2 or US3 to be built first.
- Polish comes after all stories.
- Within a story: tests, then services, then serializers, then views and urls.

## Parallel Execution Examples

- **Foundational**: T009 and T010 can run together after T005–T008.
- **US3**: T028–T032 can run together, then T033 → T034 → T035 → T036.
- **After US1**: the US5 and US6 test tasks can run in parallel with US2.

## Implementation Strategy

1. **MVP = US1–US4** (all P1): take the order, collect payments, track arrival and fulfill.
2. Then add US5 (search) and US6 (cancel and history).
3. Polish, then `/code-review` and `/security-review` before merge (CLAUDE.md).
