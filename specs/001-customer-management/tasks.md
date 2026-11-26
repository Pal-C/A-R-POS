---

description: "Task list for Customer Management (001)"
---

# Tasks: Customer Management

**Input**: Design documents from `/specs/001-customer-management/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/customers-api.md](contracts/customers-api.md),
[quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle II (non-negotiable) requires service, API,
constraint, concurrency and query-count tests. Within each story, write tests first and confirm
they fail before implementing.

**Organization**: Tasks are grouped by user story (spec.md US1–US5) so each story can be built,
tested and demonstrated on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: The user story the task belongs to (US1–US5)
- All paths are relative to the repository root

## Path Conventions

Web application: Django backend in `backend/`. This feature changes no frontend code (plan.md,
research R10).

- Customers app: `backend/customers/`, tests in `backend/customers/tests/`
- Touch points: `backend/sales/`, `backend/stringing/`, `backend/preorders/`, `backend/config/urls.py`
- Run commands from `backend/`, using `.venv/bin/python manage.py …`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test package and URL wiring for the customers app

- [X] T001 Replace `backend/customers/tests.py` with a test package: create
  `backend/customers/tests/__init__.py` and delete `backend/customers/tests.py`. This avoids the
  `tests.py`/`tests/` discovery clash.
- [X] T002 [P] Create `backend/customers/tests/factories.py` with `make_user(permissions=...)` (customers
  app permissions), `make_customer(**overrides)`, and helpers that create a finalized sale, a
  stringing order and a pre-order for a customer. Reuse `backend/sales/tests/factories.py` for
  users, products and sale lines where possible.
- [X] T003 [P] Create `backend/customers/urls.py` with an empty `urlpatterns`, and mount it as
  `path("api/customers/", include("customers.urls"))` in `backend/config/urls.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Phone normalization, the model changes and the audit table. Every story depends on
these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Write tests for phone normalization in `backend/customers/tests/test_phone.py`:
  `+63 917 123 4567`, `0917-123-4567`, `(0917) 1234567` → `09171234567`; `(02) 8123 4567` →
  `0281234567`; blank → `""`; partial `+63 917` → `0917`; bare partial `63917` stays `63917`;
  `is_phone_query()` true for `4567` and `+63 917`, false for `ana` and `ana 4567` (research R1).
- [X] T005 [P] Implement `normalize_phone(value)` and `is_phone_query(value)` in
  `backend/customers/phone.py` per research R1. Make T004 pass.
- [X] T006 Extend `Customer` in `backend/customers/models.py`:
  - add the field in data-model.md `Customer.phone_normalized`, set in `save()` from
    `Customer.phone_number` using `normalize_phone`;
  - add the `customer_full_name_not_blank` check constraint (data-model.md `Customer.full_name`);
  - add indexes `customer_phone_norm_idx` and `customer_active_name_idx` (data-model.md
    `Customer.is_active`, `Customer.full_name`);
  - add Meta permission `archive_customer`;
  - keep `Customer.created_at` and `Customer.updated_at` read-only (data-model.md).
- [X] T007 Add the `CustomerAuditEvent` model to `backend/customers/models.py`, with these
  data-model.md fields:
  - `CustomerAuditEvent.action` (TextChoices `ARCHIVED`/`REACTIVATED`/`DELETED`)
  - `CustomerAuditEvent.customer_ref` (indexed integer, not a FK)
  - `CustomerAuditEvent.customer_name`
  - `CustomerAuditEvent.performed_by` (PROTECT)
  - `CustomerAuditEvent.created_at`

  Add ordering newest first and an index on `(customer_ref, -created_at)`.
- [X] T008 Generate `backend/customers/migrations/0002_*.py` (schema for T006–T007). Hand-write
  `backend/customers/migrations/0003_backfill_phone_normalized.py`: a data migration that fills
  data-model.md `Customer.phone_normalized` for existing rows, with a no-op reverse. Run
  `manage.py migrate` and `makemigrations --check`.
- [X] T009 [P] Write constraint and model tests in `backend/customers/tests/test_models.py`:
  - a blank or whitespace-only `full_name` raises `IntegrityError` (data-model.md
    `Customer.full_name`);
  - `phone_normalized` is set on create and on update, and cleared when the phone is removed;
  - the `archive_customer` permission is registered.

**Checkpoint**: Migrations apply, and the phone and model tests pass. User stories can start.

---

## Phase 3: User Story 1 - Find a customer at the counter (Priority: P1) 🎯 MVP

**Goal**: Staff can list customers alphabetically, search by partial name or by phone in any
format, filter active/archived/all, and open a customer's details.

**Independent Test**: Seed customers with the factory. `GET /api/customers/?search=ana`,
`?search=4567` and `?search=09171234567` each return Ana. `GET /api/customers/{id}/` returns every
stored field and the timestamps.

### Tests for User Story 1 ⚠️

- [X] T010 [P] [US1] Write selector tests for `search_customers()` in
  `backend/customers/tests/test_selectors.py`:
  - name substring, case-insensitive, trimmed;
  - phone substring across formats, including a partial `+63 917` search that matches
    `0917 123 4567` (research R1);
  - `status` = `active` (default) / `archived` / `all`;
  - order by `full_name`, then `id`;
  - accented names ("Peña") found by their exact characters.
- [X] T011 [P] [US1] Write API tests for `GET /api/customers/` and `GET /api/customers/{id}/` in
  `backend/customers/tests/test_api.py`:
  - list item shape, pagination (`count`/`next`), and an invalid `status` → 400;
  - empty search returns the default list; no matches returns an empty `results` with 200;
  - the detail shape per the contract (no `summary`/`last_archive_event` yet), unknown id → 404,
    unauthenticated → 401/403;
  - query count for the list is the same with 1 and 25 customers.

### Implementation for User Story 1

- [X] T012 [US1] Implement `search_customers(query, status)` in `backend/customers/selectors.py`:
  - use `is_phone_query`/`normalize_phone` to choose between matching data-model.md
    `Customer.phone_normalized` and `Customer.full_name`;
  - filter on `Customer.is_active` by `status`;
  - raise `ValidationError` for an unknown status.
- [X] T013 [P] [US1] Create `CustomerListSerializer` and `CustomerDetailSerializer` (all fields
  read-only) in `backend/customers/serializers.py`, per contracts/customers-api.md (list item and
  detail without `summary`/`last_archive_event`). Fields come from data-model.md `Customer.*`.
- [X] T014 [US1] Implement `CustomerListCreateView` (GET only for now) and `CustomerDetailView`
  (GET) in `backend/customers/views.py`. Use `search_customers`, convert service
  `ValidationError` to 400, use `IsAuthenticated`, and return 404 for unknown ids. Register the
  routes in `backend/customers/urls.py` as `customer-list-create` and `customer-detail`.

**Checkpoint**: US1 tests pass. Staff can find any existing customer through the API.

---

## Phase 4: User Story 2 - Register a new customer (Priority: P1)

**Goal**: Staff create customers with a required name and optional contact details. Duplicate
phones trigger a warning but never block the save.

**Independent Test**: `POST /api/customers/` with only `full_name` → 201, and the customer is
active. POST a second customer with the same phone in another format → 201, and
`duplicate_phone_customers` lists the first. Both are then found by US1 search.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Write service tests for `create_customer()` in
  `backend/customers/tests/test_services.py`:
  - name trimmed, and blank or whitespace-only rejected (data-model.md `Customer.full_name`);
  - email validated (data-model.md `Customer.email`);
  - phone characters validated and the length limit enforced (data-model.md
    `Customer.phone_number`);
  - new customers are active.
- [X] T016 [P] [US2] Write tests for `phone_matches()` in `backend/customers/tests/test_selectors.py`:
  - matches on the normalized phone; active customers only; at most 5;
  - honors `exclude_id`;
  - blank or non-numeric input → empty.
- [X] T017 [P] [US2] Write API tests in `backend/customers/tests/test_api.py`:
  - `POST /api/customers/` → 201 with the detail shape plus `duplicate_phone_customers`;
  - 400 with field-keyed errors for a blank name, a bad email, or bad phone characters;
  - client-sent `is_active=false`, `created_at` and `phone_normalized` are ignored;
  - `GET /api/customers/phone-matches/`: shape, non-paginated, `[]` for a blank phone, 401
    unauthenticated.

### Implementation for User Story 2

- [X] T018 [US2] Implement `create_customer(**fields)`, with a docstring stating its side effects, in
  `backend/customers/services.py`:
  - inside `transaction.atomic`, trim fields and validate data-model.md `Customer.full_name`,
    `Customer.phone_number` and `Customer.email`;
  - return the customer.
- [X] T019 [US2] Implement `phone_matches(phone, exclude_id=None)` in
  `backend/customers/selectors.py` per research R7, using data-model.md `Customer.phone_normalized`
  and `Customer.is_active`.
- [X] T020 [US2] Add `CustomerWriteSerializer` to `backend/customers/serializers.py`. It accepts
  only `full_name`, `phone_number`, `email`, `address` and `notes`. Field rules come from
  data-model.md `Customer.full_name`, `Customer.phone_number` and `Customer.email`. Its `create()`
  calls `create_customer`.
- [X] T021 [US2] Add POST to `CustomerListCreateView` in `backend/customers/views.py`, responding 201
  with `CustomerDetailSerializer` data plus `duplicate_phone_customers` from `phone_matches`. Add
  `PhoneMatchesView`. Route it at `phone-matches/` in `backend/customers/urls.py`, **before** the
  `<int:pk>/` route.

**Checkpoint**: US1 and US2 tests pass. Customers can be registered and found. This is the MVP.

---

## Phase 5: User Story 3 - Update customer information (Priority: P2)

**Goal**: Staff edit a customer's name, phone, email, address and notes, with the same
validation as creation.

**Independent Test**: `PATCH /api/customers/{id}/` with a new phone → 200. The new number is
searchable through US1 and shows in the details.

### Tests for User Story 3 ⚠️

- [X] T022 [P] [US3] Write service tests for `update_customer()` in
  `backend/customers/tests/test_services.py`:
  - partial updates; the same validation as create;
  - a rejected update leaves the stored row unchanged;
  - `phone_normalized` is recomputed;
  - an archived customer can still be edited;
  - two updates made one after the other leave the second update's full set of values (last save
    wins, never a mix of both).
- [X] T023 [P] [US3] Write API tests in `backend/customers/tests/test_api.py`:
  - `PATCH /api/customers/{id}/` → 200 with detail plus `duplicate_phone_customers` (excluding
    itself);
  - 400 for a blank name or bad email; 404 for an unknown id;
  - `is_active`, `created_at` and `updated_at` in the body are ignored;
  - a sale linked to the customer shows the corrected name in `GET /api/sales/{id}/`
    (`customer_name`).

### Implementation for User Story 3

- [X] T024 [US3] Implement `update_customer(customer_id, **fields)`, with a docstring stating its side
  effects, in `backend/customers/services.py`:
  - inside `transaction.atomic`, `select_for_update()` the customer;
  - validate only the fields supplied (data-model.md `Customer.full_name`,
    `Customer.phone_number`, `Customer.email`);
  - never touch `Customer.is_active`.
- [X] T025 [US3] Make `CustomerDetailView` in `backend/customers/views.py` accept PATCH, using
  `CustomerWriteSerializer(partial=True)`, whose `update()` calls `update_customer`. Respond with
  detail data plus `duplicate_phone_customers` from `phone_matches(..., exclude_id=pk)`. Limit
  methods to GET, PATCH and DELETE (DELETE is wired in US5).

**Checkpoint**: US1–US3 tests pass.

---

## Phase 6: User Story 4 - View a customer's history (Priority: P2)

**Goal**: A customer's details include a summary (counts, total spent, outstanding balance, open
items), plus paginated lists of their sales, stringing orders and pre-orders. Totals use the
shared sales net-paid rule.

**Independent Test**: For a customer with one partly paid sale, one stringing order and one
pre-order with a deposit, `GET /api/customers/{id}/` shows the correct `summary`, and each history
endpoint lists its record newest first with the right amounts.

### Tests for User Story 4 ⚠️

- [X] T026 [P] [US4] Write tests in `backend/sales/tests/test_selectors.py`:
  - `net_paid_expression()` aggregate and `net_paid_subquery("sale")` annotation equal
    `Sale.amount_paid` for sales with receipts, refunds and voided payments, and for a sale with
    no payments (→ 0.00);
  - the subquery also works for `stringing_order` and `preorder` payments.
- [X] T027 [P] [US4] Write summary tests for `customer_summary()` in
  `backend/customers/tests/test_selectors.py`, against hand-computed values:
  - drafts are excluded from counts and totals; cancelled sales count but add nothing to spent
    or outstanding;
  - refunds reduce `total_spent`;
  - stringing total = price − discount; pre-order total = quantity × unit price;
  - the open pre-order and unfinished stringing counts are correct;
  - a customer with no history gets zeros.
- [X] T028 [P] [US4] Write API tests in `backend/customers/tests/test_api.py`:
  - detail includes `summary` per the contract;
  - `GET /api/customers/{id}/sales/`, `/stringing-orders/` and `/preorders/`:
    - row shapes per the contract, newest-first order, pagination, drafts excluded from sales;
    - `balance` is 0.00 for cancelled sales;
    - a customer with no history gets an empty `results`; an unknown customer → 404;
  - query counts are constant for detail (1 vs 30 transactions) and for each history list (1 vs
    25 rows).

### Implementation for User Story 4

- [X] T029 [US4] Create `backend/sales/selectors.py` with `net_paid_expression(prefix="")` and
  `net_paid_subquery(order_field)` per research R3. Both are Decimal-typed and count only posted
  payments (receipts positive, refunds negative). Point `Sale.amount_paid`'s docstring in
  `backend/sales/models.py` at it as the canonical rule.
- [X] T030 [US4] Implement `customer_summary(customer)` in `backend/customers/selectors.py`, per
  data-model.md "Derived: Customer Summary", using `net_paid_expression`. Use a fixed number of
  aggregate queries and Decimal output fields.
- [X] T031 [US4] Implement `sales_history(customer)`, `stringing_history(customer)` and
  `preorder_history(customer)` querysets in `backend/customers/selectors.py`, per data-model.md
  "Derived: history rows":
  - annotate `amount_paid`/`balance`/`total_amount` with `net_paid_subquery` and F expressions;
  - use `select_related("product")` for pre-orders;
  - order newest first.
- [X] T032 [US4] Add `CustomerSummarySerializer`, `CustomerSaleHistorySerializer`,
  `CustomerStringingHistorySerializer` and `CustomerPreorderHistorySerializer` (read-only) to
  `backend/customers/serializers.py`. Add a `summary` field to `CustomerDetailSerializer`.
- [X] T033 [US4] Add `CustomerSalesView`, `CustomerStringingOrdersView` and `CustomerPreordersView`
  (paginated `ListAPIView`s, 404 for unknown customers) to `backend/customers/views.py`. Pass
  `customer_summary` into detail responses (GET, POST, PATCH). Register `<int:pk>/sales/`,
  `<int:pk>/stringing-orders/` and `<int:pk>/preorders/` in `backend/customers/urls.py`.

**Checkpoint**: US1–US4 tests pass. The customer page data is complete apart from archiving.

---

## Phase 7: User Story 5 - Archive, reactivate, or delete customers (Priority: P3)

**Goal**:

- Managers with `archive_customer` can archive and reactivate customers.
- Managers with `delete_customer` can permanently delete customers who have no history.
- Every action is audited, and archived customers cannot be used on new transactions.

**Independent Test**:

- Archive a customer who has a completed sale: they leave the default list, their sale still
  shows them, and a new sale with them → 400. Reactivate: they're usable again.
- Deleting them → 400. Deleting a no-history customer → 204, and a `DELETED` audit event keeps
  their name.

### Tests for User Story 5 ⚠️

- [X] T034 [P] [US5] Write service tests in `backend/customers/tests/test_services.py`:
  - `archive_customer` / `reactivate_customer`: state rules (archiving twice → error; reactivating
    an active customer → error); audit events with the correct `action`, `performed_by` and
    `customer_name` (data-model.md `CustomerAuditEvent.*`);
  - archiving leaves sales, stringing orders, pre-orders and payments byte-for-byte unchanged
    (SC-005);
  - `delete_customer`:
    - refused for each history type, including a draft sale and cancelled records, with the
      "archive instead" message;
    - allowed for an archived customer with no history;
    - writes a `DELETED` event with `customer_ref` and `customer_name` before the row is removed;
  - `ensure_usable` raises for archived customers.
- [X] T035 [P] [US5] Write a delete-race test (`TransactionTestCase`, two threads) in
  `backend/customers/tests/test_concurrency.py`. One thread deletes a no-history customer while the
  other creates a draft sale for them. Assert that either the delete is refused or the sale
  fails, never a deleted customer with a sale (research R6).
- [X] T036 [P] [US5] Extend `backend/sales/tests/test_services.py`: `finalize_sale` refuses a draft
  whose customer was archived after the draft was created; `create_draft_sale` and
  `update_draft_sale` still refuse archived customers via `ensure_usable`. Assert that
  `finalize_sale` for a sale with a customer runs the same number of queries as for a walk-in sale
  with the same items, plus at most 1 (plan.md checkout-path impact).
- [X] T037 [P] [US5] Write admin form tests in `backend/customers/tests/test_admin_forms.py`.
  The stringing order and pre-order admin forms reject a newly chosen archived customer, but
  still save edits to an existing order whose customer was archived later.
- [X] T038 [P] [US5] Write API tests in `backend/customers/tests/test_api.py`:
  - archive/reactivate: 200 with `is_active` and `last_archive_event`; 400 for the wrong state;
    403 without `archive_customer`;
  - `DELETE`: 204 or 400 (has history); 403 without `delete_customer`, including for a user who
    has `archive_customer`;
  - an archived customer is absent from the default list but present with `?status=archived`;
  - `POST /api/sales/` with an archived `customer_id` → 400.

### Implementation for User Story 5

- [X] T039 [P] [US5] Change data-model.md `Sale.customer` to `on_delete=PROTECT` (still nullable)
  in `backend/sales/models.py`, and generate `backend/sales/migrations/0004_*.py`.
- [X] T040 [P] [US5] Change data-model.md `StringingOrder.customer` to `on_delete=PROTECT` (still
  nullable) in `backend/stringing/models.py`, and generate `backend/stringing/migrations/0002_*.py`.
- [X] T041 [US5] Implement `ensure_usable(customer)`, `archive_customer(customer_id, user)`,
  `reactivate_customer(customer_id, user)` and `delete_customer(customer_id, user)` in
  `backend/customers/services.py`:
  - give each function a docstring stating its side effects (audit events, deletion);
  - follow data-model.md "State transitions" and research R6 (`transaction.atomic`,
    `select_for_update`, existence checks across sales of any status, stringing orders and
    pre-orders);
  - write `CustomerAuditEvent` rows using data-model.md `CustomerAuditEvent.action`,
    `CustomerAuditEvent.customer_ref`, `CustomerAuditEvent.customer_name` and
    `CustomerAuditEvent.performed_by`.
- [X] T042 [US5] In `backend/sales/services.py`, replace the inline "customer is archived" checks in
  `create_draft_sale` and `update_draft_sale` with `customers.services.ensure_usable`, and call it
  in `finalize_sale` when the sale has a customer.
- [X] T043 [P] [US5] Add a `ModelAdmin` with form validation to `backend/stringing/admin.py` and
  `backend/preorders/admin.py`. The form calls `ensure_usable` only when `customer` is new or
  changed (research R9).
- [X] T044 [US5] Add `last_archive_event` (latest `ARCHIVED`/`REACTIVATED` `CustomerAuditEvent` for
  the customer, with `performed_by_name`) to `CustomerDetailSerializer` in
  `backend/customers/serializers.py`, with a selector `last_archive_event(customer)` in
  `backend/customers/selectors.py`.
- [X] T045 [US5] Add the following to `backend/customers/views.py`:
  - `ArchiveCustomerView` and `ReactivateCustomerView`, requiring `customers.archive_customer`;
  - DELETE on `CustomerDetailView`, requiring `customers.delete_customer` and calling
    `delete_customer` (204 on success, 400 on history).

  Register `<int:pk>/archive/` and `<int:pk>/reactivate/` in `backend/customers/urls.py`.

**Checkpoint**: All five stories pass their tests independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Workflow coverage, admin, and final validation

- [X] T046 [P] Write the story-level workflow test in `backend/customers/tests/test_workflow.py`,
  per quickstart.md: create → find by phone variants → edit → finalize and partly pay a sale →
  check summary and history → archive (new sale refused) → reactivate → delete refused → delete a
  no-history customer → audit event exists.
- [X] T047 [P] Register `Customer` (search on name and phone, filter on `is_active`, normalized phone
  read-only) and `CustomerAuditEvent` (fully read-only: no add, change or delete permissions) in
  `backend/customers/admin.py`.
- [X] T048 Run `.venv/bin/ruff check .`, `manage.py makemigrations --check --dry-run` and
  `manage.py test customers sales inventory catalog` from `backend/`. Fix any failures.
- [X] T049 Run the manual smoke test and the **required** performance check in
  `specs/001-customer-management/quickstart.md`. Record the measured timings for SC-002 and SC-004
  in the PR description.

---

- [X] T050 [P] Write an authentication sweep in `backend/customers/tests/test_auth.py`. Loop over
  every endpoint and method in contracts/customers-api.md (list/create, detail GET/PATCH/DELETE,
  archive, reactivate, the three history lists, phone-matches) and assert that each returns
  401/403 unauthenticated and changes no data. This satisfies constitution Principle II for every
  endpoint.

**Verified in the frontend feature, not here** (research R10): FR-015's confirmation step,
FR-018's open-items warning, the spec's Screen States table, and SC-001, SC-003 and SC-006. This
feature supplies their data.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. **Blocks all stories** (the model, migrations and
  `phone.py` are used everywhere).
- **US1 (Phase 3)**: depends on Foundational only.
- **US2 (Phase 4)**: depends on Foundational. It shares `views.py` and `serializers.py` with US1,
  so build it after US1 or coordinate edits to those files.
- **US3 (Phase 5)**: depends on US2's `CustomerWriteSerializer` (T020) and `phone_matches` (T019).
- **US4 (Phase 6)**: depends on Foundational and on US1's detail view (T014). It is independent
  of US2 and US3.
- **US5 (Phase 7)**: depends on Foundational and on US1's detail view (T014). Its sales changes
  (T039, T042) are independent of US2–US4.
- **Polish (Phase 8)**: depends on all stories. T050 needs every endpoint, so it runs last.

### Story completion order

```text
Setup → Foundational → US1 ─┬─▶ US2 ─▶ US3
                            ├─▶ US4
                            └─▶ US5
                                     └─▶ Polish (after all)
```

### Within each story

- Tests first, and they must fail; then selectors and services; then serializers; then views and
  URLs.
- Tasks that edit the same file (`views.py`, `serializers.py`, `selectors.py`, `services.py`) run
  in order, even across stories.

### Parallel Opportunities

- **Setup**: T002 and T003.
- **Foundational**: T004 and T005 (phone tests and implementation, separate files); T009 alongside
  the migration once T006–T007 are done.
- **US1**: T010 and T011 (tests); T013 (serializers) alongside T012 (selectors).
- **US2**: T015, T016 and T017 (tests in three files).
- **US4**: T026, T027 and T028 (tests); T029 (`sales/selectors.py`) alongside other work.
- **US5**: T034–T038 (tests in separate files); T039, T040 and T043 (different apps).
- **Across stories**: once US1 is done, US4 and US5 can proceed in parallel with US2/US3, because
  they touch different selector and service functions. Merge the shared-file edits in order.

---

## Parallel Example: User Story 5

```bash
# Tests together (different files):
Task: "T034 service tests in backend/customers/tests/test_services.py"
Task: "T036 sales finalize tests in backend/sales/tests/test_services.py"
Task: "T037 admin form tests in backend/customers/tests/test_admin_forms.py"
Task: "T038 API tests in backend/customers/tests/test_api.py"

# Model changes together (different apps):
Task: "T039 Sale.customer PROTECT in backend/sales/models.py"
Task: "T040 StringingOrder.customer PROTECT in backend/stringing/models.py"
Task: "T043 admin forms in backend/stringing/admin.py and backend/preorders/admin.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2, both P1)

1. Phase 1 Setup, then Phase 2 Foundational.
2. Phase 3 (US1): find customers. **Validate**: search tests pass.
3. Phase 4 (US2): register customers. **Validate**: create plus search round trip.
4. **STOP**: this is a usable MVP. Counter staff can register and find customers, and sales can
   already reference them.

### Incremental Delivery

1. MVP (US1 + US2).
2. Add US3 (edit) and validate.
3. Add US4 (history and summary) and validate. This is the biggest user-facing value after the MVP.
4. Add US5 (archive, reactivate, delete and FK hardening) and validate.
5. Polish: workflow test, admin, full suite, quickstart.

Commit after each task or logical group. The test-first tasks make a natural pair of commits:
`test(customers): …` then `feat(customers): …`.

---

## Notes

- `[P]` = different files and no dependency on an incomplete task.
- Story labels trace each task back to spec.md user stories.
- data-model.md is the canonical source for field rules. Tasks cite `Entity.field` instead of
  repeating them, and only state rules that narrow them (e.g., the allowed phone characters in
  T020).
- Out of scope (spec Assumptions, plan R10): frontend screens, customer merge, stringing and
  pre-order create APIs.
