---

description: "Task list for Stringing Management (002)"
---

# Tasks: Stringing Management

**Input**: Design documents from `/specs/002-stringing-management/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/stringing-api.md](contracts/stringing-api.md),
[quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle II (non-negotiable) requires service, API,
constraint, concurrency and query-count tests. Within each story, write tests first and confirm
they fail before implementing.

**Organization**: Tasks are grouped by user story (spec.md US1–US6) so each story can be built,
tested and demonstrated on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: The user story the task belongs to (US1–US6)
- All paths are relative to the repository root

## Path Conventions

Web application: Django backend in `backend/`. This feature changes no frontend code
([research R9](research.md#r9-frontend-scope)).

---

## Phase 1: Setup

**Purpose**: App skeleton and settings

- [X] T001 Add `STORE_TIME_ZONE = "Asia/Manila"` (env-overridable, default as given) to `backend/config/settings.py` ([R3](research.md#r3-revenue-and-profit-report-fr-026029-q1))
- [X] T002 [P] Create the empty modules `backend/stringing/services.py`, `backend/stringing/selectors.py`, `backend/stringing/serializers.py` and `backend/stringing/urls.py` (empty `urlpatterns`). Replace the placeholder `backend/stringing/views.py` with an empty module, and create the `backend/stringing/tests/__init__.py` package
- [X] T003 Mount `path("api/stringing/", include("stringing.urls"))` in `backend/config/urls.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, permissions, shared helpers and factories that every story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Extend `StringingOrder` in `backend/stringing/models.py` as follows:
  - Add `notes`, `updated_at`, `ready_at`, `paid_in_full_at`, `cancelled_at` and `cancelled_by`
    per data-model.md `StringingOrder.notes`, `StringingOrder.updated_at`, `StringingOrder.ready_at`,
    `StringingOrder.paid_in_full_at`, `StringingOrder.cancelled_at` and `StringingOrder.cancelled_by`.
  - Add the new constraints `stringing_racket_not_blank` (data-model.md
    `StringingOrder.racket_description`), `stringing_string_type_not_blank` (data-model.md
    `StringingOrder.string_type`), `stringing_cancel_fields_consistent` (data-model.md
    `StringingOrder.status`, `StringingOrder.cancelled_at`, `StringingOrder.cancellation_reason`)
    and `stringing_completed_has_time` (data-model.md `StringingOrder.completed_at`).
  - Add the indexes from data-model.md.
  - Move `permissions` inside `Meta` as `cancel_stringingorder` and `view_stringing_financials`
    ([R6](research.md#r6-permissions-fr-030)).
  - Add a docstring for the `total_amount` property.
- [X] T005 Add the `StringingOrderEvent` model to `backend/stringing/models.py`, with
  `EventType` TextChoices and fields per data-model.md `StringingOrderEvent.order`,
  `StringingOrderEvent.event_type`, `StringingOrderEvent.from_status`,
  `StringingOrderEvent.to_status`, `StringingOrderEvent.changes`, `StringingOrderEvent.reason`,
  `StringingOrderEvent.performed_by` and `StringingOrderEvent.created_at`. Add the
  `(order, created_at)` index.
- [X] T006 Generate the schema migration `backend/stringing/migrations/0003_stringing_management.py`
  with `makemigrations stringing`, and review it: no edits to 0001/0002.
- [X] T007 Write migration `backend/stringing/migrations/0004_order_number_seq.py`. It uses `RunSQL`
  to `CREATE SEQUENCE stringing_order_number_seq`, starting above the highest numeric suffix of
  existing `STR-` order numbers, and includes a reverse `DROP SEQUENCE`
  ([R1](research.md#r1-order-number-generation-fr-002-sc-002), [R8](research.md#r8-data-migration-for-existing-rows)).
- [X] T008 Write data migration `backend/stringing/migrations/0005_backfill_payment_state.py`:
  - Set `paid_in_full_at` (data-model.md `StringingOrder.paid_in_full_at`) to the latest posted
    payment date for fully paid orders, or to `created_at` for zero-total orders.
  - Set `updated_at` = `created_at`.
  - Include a no-op reverse ([R8](research.md#r8-data-migration-for-existing-rows)).
- [X] T009 [P] Create `backend/stringing/tests/factories.py` with `make_user(perms=...)`,
  `make_customer`, `make_order(**overrides)` and `make_payment(order, amount, type=RECEIPT)`. Update
  `make_stringing_order` in `backend/customers/tests/factories.py` to delegate to it, keeping its
  signature.
- [X] T010 [P] Write constraint tests in `backend/stringing/tests/test_models.py`: each new
  constraint rejects invalid data, and the existing price, discount and cost constraints are
  covered. Also check that both new permissions exist after migrate.
- [X] T011 Add the order-annotation helper `annotate_payment_state(queryset)` in
  `backend/stringing/selectors.py`. It adds `amount_paid` with `sales.selectors.net_paid_subquery("stringing_order")`,
  plus `balance`, `refund_due` and `payment_state` per data-model.md (Derived). Also add
  `order_queryset()` with `select_related("customer", "created_by", "cancelled_by")`.
- [X] T012 Add the service helpers in `backend/stringing/services.py`:
  - `_lock_order(order_id)`, using `select_for_update`;
  - `_net_paid(order)`, using the shared net-paid rule;
  - `_record_event(order, user, event_type, **fields)`;
  - `sync_payment_state(order)`, which sets or clears `paid_in_full_at` when the balance reaches or
    leaves 0.00 ([R2](research.md#r2-where-payments-are-recorded-and-how-paid-in-full-is-tracked-fr-014017-fr-028)).
  Each public helper gets a docstring stating its side effects.
- [X] T013 Add the serializer base in `backend/stringing/serializers.py`. It covers
  `StringingOrderDetailSerializer` and `StringingOrderListSerializer` per the contract's order
  representation. It masks `direct_cost`/`profit` unless the request user has
  `stringing.view_stringing_financials`, and adds a `run_service`-style helper that converts Django
  `ValidationError` to DRF (reuse the customers pattern).

**Checkpoint**: migrations apply; `manage.py test stringing customers sales` passes.

---

## Phase 3: User Story 1 - Take in a racket for stringing (Priority: P1) 🎯 MVP

**Goal**: Staff create stringing orders (customer or walk-in) with racket, string, tension and
money fields, get a unique order number, view details, and edit before completion.

**Independent Test**: Create an order for a customer and a walk-in. Each gets a distinct
`STR-YYYY-NNNNNN`, status RECEIVED and the correct total. An archived customer is refused.

### Tests for User Story 1

- [X] T014 [P] [US1] Write service tests in `backend/stringing/tests/test_services.py` for
  `create_stringing_order`:
  - success with and without a customer;
  - order number format and increment;
  - each validation rejection: blank racket or string, negative price/discount/cost,
    discount > price;
  - archived customer refused;
  - a CREATED event is written;
  - a zero-total order gets `paid_in_full_at`.
  Also cover `update_stringing_order`:
  - field changes are written to an UPDATED event with old and new values;
  - the order is refused when COMPLETED or CANCELLED;
  - a new total below net paid is refused;
  - a discount edit to a fully paid total sets `paid_in_full_at`, and a price increase clears it.
- [X] T015 [P] [US1] Write API tests in `backend/stringing/tests/test_api.py` for POST
  `/api/stringing/orders/`, GET `/{id}/` and PATCH `/{id}/`:
  - 201/200 response shapes per contract;
  - 400 field errors;
  - 404 for an unknown id;
  - 405 on DELETE;
  - `direct_cost` and `profit` are omitted without the financials permission;
  - PATCH of `direct_cost` without the permission returns 403;
  - a query-count assertion on the detail view.
- [X] T016 [P] [US1] Write a concurrency test in `backend/stringing/tests/test_concurrency.py`
  (`TransactionTestCase`): parallel `create_stringing_order` calls in threads produce distinct order
  numbers (SC-002).

### Implementation for User Story 1

- [X] T017 [US1] Implement `create_stringing_order(*, user, **fields)` in
  `backend/stringing/services.py`:
  - take `nextval('stringing_order_number_seq')` and format the number per data-model.md
    `StringingOrder.order_number` (year in `STORE_TIME_ZONE`);
  - validate the fields per data-model.md `StringingOrder.racket_description`,
    `StringingOrder.string_type`, `StringingOrder.tension`, `StringingOrder.service_price`,
    `StringingOrder.discount_amount` and `StringingOrder.direct_cost` (strip text; field-keyed
    `ValidationError`);
  - check data-model.md `StringingOrder.customer` with `customers.services.ensure_usable`;
  - write a CREATED event and call `sync_payment_state`.
- [X] T018 [US1] Implement `update_stringing_order(*, order_id, user, **changes)` in
  `backend/stringing/services.py`:
  - lock the row;
  - refuse COMPLETED and CANCELLED orders (data-model.md `StringingOrder.status`);
  - apply the same validation as create, plus `ensure_usable` on a customer change;
  - refuse a new total below net paid (FR-008);
  - record an UPDATED event with `{field: [old, new]}` (money as strings);
  - call `sync_payment_state`.
- [X] T019 [US1] Add `StringingOrderWriteSerializer` (create/partial-update input only) in
  `backend/stringing/serializers.py`.
- [X] T020 [US1] Implement `StringingOrderListCreateView` (POST only for now; GET is added in US4)
  and `StringingOrderDetailView` (GET/PATCH; no DELETE). Include the PATCH `direct_cost` permission
  check (403). Put the views in `backend/stringing/views.py` and route them in
  `backend/stringing/urls.py`.
- [X] T021 [US1] Make `backend/stringing/admin.py` read-only for audit purposes: disable delete
  and register `StringingOrderEvent` read-only.

**Checkpoint**: US1 tests pass; orders can be created, viewed and edited through the API.

---

## Phase 4: User Story 2 - Move an order through the workshop (Priority: P1)

**Goal**: One-step status workflow with step-back correction; pickup only when paid in full;
every change audited.

**Independent Test**: Walk an order RECEIVED → IN_PROGRESS → READY → (pay) → COMPLETED. Skipping,
moving out of a final state, and completing with a balance are each refused.

### Tests for User Story 2

- [X] T022 [P] [US2] Add `change_status` service tests to `backend/stringing/tests/test_services.py`:
  - every allowed transition, including both step-backs;
  - every disallowed transition (skips, from COMPLETED, from CANCELLED, to CANCELLED);
  - COMPLETED refused while the balance is above 0 and allowed at 0;
  - `ready_at` is set or cleared and `completed_at` is set;
  - a STATUS_CHANGED event is written;
  - a stale `expected_status` is refused.
- [X] T023 [P] [US2] Add API tests for POST `/api/stringing/orders/{id}/status/` to
  `backend/stringing/tests/test_api.py`: 200 shape, 400 messages (allowed next statuses, balance
  owed, `current_status` on a stale request), 404, 401.

### Implementation for User Story 2

- [X] T024 [US2] Implement the `ALLOWED_TRANSITIONS` table and
  `change_status(*, order_id, user, to_status, expected_status=None)` in
  `backend/stringing/services.py`:
  - lock the row;
  - check the transition per data-model.md `StringingOrder.status` (State transitions);
  - refuse COMPLETED unless net paid ≥ total (FR-013);
  - maintain data-model.md `StringingOrder.ready_at` and `StringingOrder.completed_at`;
  - write a STATUS_CHANGED event.
- [X] T025 [US2] Add `StatusChangeSerializer` in `backend/stringing/serializers.py` and
  `StringingOrderStatusView` in `backend/stringing/views.py`. Route it in `backend/stringing/urls.py`.

**Checkpoint**: US1 + US2 tests pass.

---

## Phase 5: User Story 3 - Take payment, in parts or in full (Priority: P1)

**Goal**: Record receipts and refunds against an order; show amount paid, balance and payment
state; keep `paid_in_full_at` correct regardless of the endpoint used.

**Independent Test**: On a 400.00 order, record 150.00 (PARTIAL, balance 250.00); 300.00 is refused;
250.00 gives PAID with `paid_in_full_at` set; a refund clears it.

### Tests for User Story 3

- [X] T026 [P] [US3] Add payment service tests to `backend/stringing/tests/test_services.py` for
  `record_order_payment`:
  - partial, then full payment;
  - over-balance refused;
  - zero, negative and unknown method refused;
  - receipt on a CANCELLED order refused;
  - refund without a reason refused;
  - refund above net paid refused;
  - `paid_in_full_at` set on the full payment and cleared by a refund.
- [X] T027 [P] [US3] Add API tests for GET/POST `/api/stringing/orders/{id}/payments/` to
  `backend/stringing/tests/test_api.py`:
  - 201 response with `payment` and the updated `order`;
  - 403 for a receipt without `sales.record_payment`;
  - 403 for a refund without `sales.process_refund`;
  - 400 cases;
  - a paged GET.
- [X] T028 [P] [US3] Add regression tests in `backend/sales/tests/test_services.py`: a stringing
  payment via `sales.services.record_payment` updates `paid_in_full_at`, and a sale payment's query
  count is unchanged. Add to `backend/sales/tests/test_sales_api.py`: a receipt on
  `/api/sales/payments/` without `sales.record_payment` returns 403. Update existing sales API tests
  to grant the permission.
- [X] T029 [P] [US3] Add a concurrency test to `backend/stringing/tests/test_concurrency.py`: two
  parallel receipts that together exceed the balance. One succeeds, and the total net paid never
  exceeds the order total.

### Implementation for User Story 3

- [X] T030 [US3] In `backend/sales/services.py`, make `record_payment` call
  `stringing.services.sync_payment_state(order)` for stringing targets after creating the payment,
  inside the same transaction. Update its docstring.
- [X] T031 [US3] In `backend/sales/views.py`, require `sales.record_payment` for RECEIPT on
  `PaymentListCreateView.create` ([R6](research.md#r6-permissions-fr-030)).
- [X] T032 [US3] Implement `record_order_payment(*, order_id, user, payment_type, amount,
  payment_method, reference_number="", notes="", reason="")` in `backend/stringing/services.py`.
  It delegates to `sales.services.record_payment` / `process_refund` (lazy import) and returns
  `(payment, order)`.
- [X] T033 [US3] Add `OrderPaymentCreateSerializer` to `backend/stringing/serializers.py` (it
  reuses `sales.serializers.PaymentSerializer` for output). Add `StringingOrderPaymentsView` (GET
  paged / POST with the receipt or refund permission check) to `backend/stringing/views.py`, and
  route it in `backend/stringing/urls.py`.

**Checkpoint**: US1–US3 tests pass. This is the P1 MVP: intake → workshop → paid pickup.

---

## Phase 6: User Story 4 - Find orders (Priority: P2)

**Goal**: Search by order number, customer name or phone, racket or string; filter by status,
payment state, customer and dates; paged, newest first.

**Independent Test**: With mixed orders, `?status=READY&search=<phone in another format>` returns
only the matching orders. A query with no match returns an empty page.

### Tests for User Story 4

- [X] T034 [P] [US4] Write selector tests in `backend/stringing/tests/test_selectors.py` for
  `search_orders`:
  - each search field;
  - phone normalization (spaces, dashes, +63);
  - multi-status filter;
  - each `payment_state`;
  - customer filter;
  - inclusive store-local date range;
  - each ordering;
  - invalid values raise `ValidationError`;
  - walk-in orders found by number, racket and string.
- [X] T035 [P] [US4] Add list API tests to `backend/stringing/tests/test_api.py`: GET
  `/api/stringing/orders/` pagination shape, 400 on invalid filters, an empty result, 401, and a
  query-count assertion constant across page sizes.

### Implementation for User Story 4

- [X] T036 [US4] Implement `search_orders(params)` in `backend/stringing/selectors.py`
  ([R7](research.md#r7-search-and-filtering-fr-018020-sc-003)). Reuse
  `customers.phone.normalize_phone` and `is_phone_query`, and `annotate_payment_state`.
- [X] T037 [US4] Add GET to `StringingOrderListCreateView` in `backend/stringing/views.py`, using
  `search_orders` and the list serializer.

**Checkpoint**: US4 tests pass.

---

## Phase 7: User Story 5 - Cancel an order with a reason (Priority: P2)

**Goal**: Permitted users cancel non-final orders with a reason. Payments are untouched, refund due
is shown, and a full audit history is viewable.

**Independent Test**: Cancel a paid READY order with a reason. The status is CANCELLED, the reason,
user and time are recorded, `refund_due` equals the amount paid, a receipt is refused, a refund is
allowed, and the history shows every step.

### Tests for User Story 5

- [X] T038 [P] [US5] Add `cancel_stringing_order` service tests to
  `backend/stringing/tests/test_services.py`:
  - success from RECEIVED, IN_PROGRESS and READY;
  - blank or whitespace reason refused;
  - COMPLETED and CANCELLED refused;
  - payments unchanged and `refund_due` correct;
  - CANCELLED event written;
  - edits and status changes refused afterwards.
  Add `order_history` selector tests to `backend/stringing/tests/test_selectors.py`: events and
  payments merged in time order, and `direct_cost` changes masked without the permission.
- [X] T039 [P] [US5] Add API tests to `backend/stringing/tests/test_api.py` for POST `/cancel/`
  (200, 400, 403 without `stringing.cancel_stringingorder`, 404) and GET `/history/` (shape,
  masking, 404, 401).

### Implementation for User Story 5

- [X] T040 [US5] Implement `cancel_stringing_order(*, order_id, user, reason)` in
  `backend/stringing/services.py`:
  - lock the row;
  - require a non-blank reason;
  - refuse final states;
  - set data-model.md `StringingOrder.status`, `StringingOrder.cancelled_at`,
    `StringingOrder.cancelled_by` and `StringingOrder.cancellation_reason`;
  - clear `paid_in_full_at` so the order leaves revenue (FR-027);
  - write a CANCELLED event.
- [X] T041 [US5] Implement `order_history(order, *, can_view_financials)` in
  `backend/stringing/selectors.py`. It merges `StringingOrderEvent` rows and payments in time order
  per the contract.
- [X] T042 [US5] Add `CancelSerializer` and `HistoryEntrySerializer` in
  `backend/stringing/serializers.py`. Add `StringingOrderCancelView` (permission
  `stringing.cancel_stringingorder`) and `StringingOrderHistoryView` in
  `backend/stringing/views.py`, and route them in `backend/stringing/urls.py`.

**Checkpoint**: US5 tests pass.

---

## Phase 8: User Story 6 - See stringing revenue and profit (Priority: P3)

**Goal**: Revenue, discounts, direct cost and profit for a date range, counting orders once they
are paid in full, with cancelled and not-yet-paid figures shown separately.

**Independent Test**: Four orders in a range (two fully paid, one partial, one cancelled after full
payment). The report counts only the two fully paid orders, and profit matches a hand calculation.

### Tests for User Story 6

- [X] T043 [P] [US6] Write `revenue_report` selector tests in
  `backend/stringing/tests/test_selectors.py`:
  - only non-cancelled orders with `paid_in_full_at` in range are counted;
  - store-local day boundaries (an order paid at 23:30 Manila lands on that day);
  - cancelled_count;
  - unpaid_count / outstanding_balance;
  - empty range returns zeros;
  - date_from > date_to raises;
  - query count ≤ 3.
- [X] T044 [P] [US6] Add API tests to `backend/stringing/tests/test_api.py` for GET
  `/api/stringing/reports/revenue/`: 200 shape, 400 on missing or invalid dates, 403 without
  `stringing.view_stringing_financials`, 401.

### Implementation for User Story 6

- [X] T045 [US6] Implement `revenue_report(date_from, date_to)` in
  `backend/stringing/selectors.py` per [R3](research.md#r3-revenue-and-profit-report-fr-026029-q1),
  using data-model.md `StringingOrder.paid_in_full_at` and `StringingOrder.cancelled_at`.
- [X] T046 [US6] Add `RevenueReportQuerySerializer` / `RevenueReportSerializer` in
  `backend/stringing/serializers.py` and `StringingRevenueReportView` in
  `backend/stringing/views.py`. Route `reports/revenue/` in `backend/stringing/urls.py`.

**Checkpoint**: all story tests pass.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T047 [P] Write an end-to-end workflow test in `backend/stringing/tests/test_workflow.py`
  following the quickstart walkthrough (intake → status → partial and full payment → complete;
  a second order cancelled and refunded; the report checked).
- [X] T048 [P] Write a 401 test for every stringing endpoint in
  `backend/stringing/tests/test_auth.py` (table-driven, as in customers).
- [X] T049 Run `python manage.py test` (all apps), `ruff check . && ruff format --check .`
  and `python manage.py makemigrations --check --dry-run` from `backend/`. Fix any failures.
- [X] T050 Confirm `backend/customers` history and summary still pass with the new fields
  (`customers/selectors.py` uses `StringingOrder`). Adjust `CustomerStringingHistorySerializer`
  only if a field rename requires it.
- [X] T051 Run the [quickstart](quickstart.md) manual API walkthrough and tick each step.
  _Done as the automated `test_workflow.py` run, which follows every quickstart step; the steps
  were not repeated by hand against a running dev server._

---

## Phase 10: Review Follow-ups (decided 2026-11-26)

- [X] T052 Fix code-review nits in `backend/stringing/selectors.py` and `backend/stringing/services.py`:
  - reject non-ASCII digits in the `customer` filter;
  - keep refund `notes` together with the reason;
  - use `payment_date` for payments in order history.
  Tests are in `backend/stringing/tests/`.
- [X] T053 Add data migration `backend/sales/migrations/0005_grant_record_payment.py`. It grants
  `sales.record_payment` to every existing active user so the counter keeps working after deploy.
  Test: `backend/sales/tests/test_migrations.py`.
- [X] T054 Completed orders stay settled after a refund:
  - `sync_payment_state` in `backend/stringing/services.py` keeps `paid_in_full_at` for COMPLETED
    orders;
  - balance shows 0 and payment state shows PAID in `backend/stringing/serializers.py` and
    `backend/stringing/selectors.py`;
  - completed orders are excluded from the outstanding balance in `backend/customers/selectors.py`.
- [X] T055 Add `total_refunds`, `net_revenue_after_refunds` and `profit_after_refunds` (refunds after
  pickup, by refund date) to `revenue_report` in `backend/stringing/selectors.py` and to the report
  serializer. Update spec FR-028, research R3, the contract and the data model.

- [X] T056 Second-review follow-ups:
  - add `StringingOrder.is_settled` in `backend/stringing/models.py`;
  - refuse receipts on settled orders in `backend/sales/services.py`;
  - apply the settled rule in the stringing selectors and serializers and in
    `backend/customers/selectors.py`, so legacy unpaid completed orders keep their real balance;
  - exclude cancelled orders from the `payment_state` filter.

---

## Dependencies & Execution Order

- **Setup (T001–T003)** → **Foundational (T004–T013)** → user stories.
- **US1** (T014–T021) comes first among the stories: create and detail are used by every later
  story's API tests.
- **US2** depends on US1. Its completion rule needs net paid, which tests set up with
  `make_payment`, so it does not need US3.
- **US3** depends on US1 only. It can proceed in parallel with US2 (different service functions,
  but the same files, so coordinate edits).
- **US4**, **US5** and **US6** each depend on US1 only. US5's history includes payments, which
  tests create with factories.
- **Polish** comes after all stories.

Within each story: tests → services → serializers → views/urls.

## Parallel Execution Examples

- **Foundational**: T009 (factories) and T010 (constraint tests) in parallel once T004–T006 land.
- **US1**: T014, T015 and T016 in parallel (different test files), then T017 → T018 → T019 →
  T020.
- **US3**: T026, T027, T028 and T029 in parallel. Then T030 and T031 (sales app) in parallel with
  T032 (stringing app).
- **After US1**: the US4 (T034–T037), US6 (T043–T046) and US5 test tasks can be written in
  parallel by different developers.

## Implementation Strategy

1. **MVP = US1 + US2 + US3** (all P1). Intake, workshop status and paid pickup are a usable
   service on their own. Stop and validate at the Phase 5 checkpoint.
2. Add **US4** (search) and **US5** (cancel + audit history). Validate each at its checkpoint.
3. Add **US6** (report) last; it only reads data.
4. Finish with Polish, then `/code-review` and `/security-review` before merge (CLAUDE.md).
