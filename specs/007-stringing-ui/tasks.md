---
description: "Task list for Stringing Order Screens"
---

# Tasks: Stringing Order Screens

**Input**: Design documents from `/specs/007-stringing-ui/`

**Tests**: Required (constitution II). Write tests first and see them fail.

**Organization**:

- US1: take in a racket
- US2: browse and find orders
- US3: update progress and hand over
- US4: cancel an order

---

## Phase 1: Setup

- [X] T001 Create frontend/src/features/stringing/ and frontend/src/styles/components/_stringing.scss. Import the partial in frontend/src/styles/main.scss.
- [X] T002 Move the shared pieces out of Sales, with no behaviour change (research R8):
  - `features/sales/CustomerPicker.tsx` → frontend/src/components/CustomerPicker.tsx. Export a `CustomerChoice` type and make `CartCustomer` an alias for it.
  - `features/sales/LeaveGuard.tsx` → frontend/src/components/LeaveGuard.tsx, with a `title` prop. Sales passes "Leave this sale?".
  - `PAYMENT_METHODS` and `paymentMethodLabel` → frontend/src/lib/payments.ts.
  - `todayInStore` → frontend/src/lib/format.ts.

  Update every Sales import. The existing Sales tests must still pass.

---

## Phase 2: Foundational (blocks all stories)

### Tests first

- [X] T003 [P] Write model tests in backend/stringing/tests/test_addons.py:
  - each new constraint rejects invalid data:
    - data-model.md StringingOrder.stencil_price, StringingOrder.grip_price (non-negative, and 0 unless the add-on is selected);
    - StringingOrder.discount_amount (≤ service + add-ons);
    - StringingOrder.materials_used (null unless cancelled);
    - StringingOrder.client_transaction_id (unique);
  - `total_amount` includes add-ons;
  - an order created with no add-on fields keeps `total = service − discount`.
- [X] T004 [P] Write unit tests in frontend/src/features/stringing/orderForm.test.ts and frontend/src/features/stringing/stringingDisplay.test.ts:
  - totals with and without add-ons, store discount and deposit;
  - the tick and untick pre-fill transitions;
  - every `validateOrder` rule;
  - `ALLOWED_MOVES` equals the backend map (research R6);
  - `stringLabel` with and without tension and colour;
  - `addOnsLabel`.

### Implementation

- [X] T005 Make the model changes in backend/stringing/models.py:
  - add StringingOrder.string_color, string_from_store, has_stencil, stencil_price, has_grip, grip_price, materials_used and client_transaction_id (data-model.md StringingOrder.*);
  - update `total_amount` and add `add_ons_total`.

  Generate backend/stringing/migrations/0007_order_addons.py, which adds the fields, drops `stringing_discount_not_above_price` and adds the five constraints from data-model.md. One migration is enough because the defaults keep every existing row valid. T003 must pass.
- [X] T006 Change `ORDER_TOTAL` in backend/stringing/selectors.py to include `stencil_price + grip_price`. In backend/stringing/services.py:
  - add the new fields to `TEXT_FIELDS`/`MONEY_FIELDS`/`EDITABLE_FIELDS`, with booleans handled in `_clean` and `_audit_value`;
  - extend `_clean` with the add-on price rules (data-model.md StringingOrder.stencil_price, StringingOrder.grip_price) and discount ≤ service + add-ons;
  - the update service's new-total check uses add-ons.

  Run the existing stringing tests; they must stay green.
- [X] T007 Update backend/stringing/serializers.py:
  - output: the new fields plus `add_ons_total`;
  - input: the new fields in `StringingOrderWriteSerializer`.
- [X] T008 Implement frontend/src/features/stringing/orderForm.ts and frontend/src/features/stringing/stringingDisplay.ts (data-model.md "Frontend form model" and "Status display"). Add the stringing defaults to frontend/src/config.ts (research R2). T004 must pass.
- [X] T009 Update frontend/src/api/stringing.ts according to contracts/stringing-api.md "Frontend client":
  - new fields;
  - `StringingOrderCreate`;
  - the `cancel` body;
  - `statusCounts` and `stringingKeys.counts`;
  - `gross_add_ons`.

  Add the matching cases to frontend/src/api/domain.test.ts. Create frontend/src/features/stringing/hooks.ts with `useStringingOrders`, `useStringingOrder`, `useStatusCounts`, `useOrderPayments` and `invalidateAfterStringing`.

---

## Phase 3: User Story 1 - Take in a racket (P1) 🎯 MVP

### Tests

- [X] T010 [P] [US1] Write service and API tests in backend/stringing/tests/test_create_deposit.py:
  - create with add-ons and a deposit: amount paid, balance and one RECEIPT payment;
  - each deposit rejection (≤ 0, above total) and each field error saves no order and no payment;
  - an idempotent repeat returns 200 with the same order;
  - reuse of the key by another user is a 400;
  - a deposit without `sales.record_payment` is a 403;
  - a zero total is paid in full;
  - the create query count.

  Add a `TransactionTestCase` for two concurrent creates with the same `client_transaction_id`.
- [X] T011 [P] [US1] Write integration tests in frontend/src/features/stringing/StringingOrderFormPage.test.tsx (MSW + axe):
  - the Invoice panel updates on tick and override;
  - inline field errors from the client and the server;
  - deposit fields hidden without the permission;
  - a double click sends one request with the same `client_transaction_id`;
  - success navigates to the list with Details open and shows a toast;
  - the leave guard;
  - edit mode sends only changed fields and offers no deposit.

### Implementation

- [X] T012 [US1] Add `take_in_order` (wrapping the unchanged `create_stringing_order`) in backend/stringing/services.py:
  - `deposit` and `client_transaction_id` (data-model.md StringingOrder.client_transaction_id; research R3);
  - an idempotent lookup scoped to the user;
  - a permission check;
  - the deposit through `sales.services.record_payment` in the same atomic block.

  In backend/stringing/serializers.py add `DepositSerializer`, and `deposit`/`client_transaction_id` on create. In backend/stringing/views.py, create returns 201 or 200 and resolves an `IntegrityError` race as sales `CheckoutView` does. T010 must pass.
- [X] T013 [US1] Build frontend/src/features/stringing/InvoicePanel.tsx and frontend/src/features/stringing/StringingOrderFormPage.tsx, laid out like Create SO:
  - Order Details card: `CustomerPicker`, racket, string model, colour, tension, add-on and store checkboxes with editable prices, notes, and the info `Banner`;
  - Invoice card: lines, total, deposit amount, method and reference (only with `sales.record_payment`), balance due, Cancel and Create Order.

  Edit mode (`:id/edit`) loads the order, refuses final orders, and PATCHes only the diff. Add styles in _stringing.scss using tokens only. T011 must pass.
- [X] T014 [US1] In frontend/src/routes/workAreas.ts, make `/stringing` load `StringingOrdersPage`, and add the children `new` ("Create a Stringing Order" / "Record the customer, racket, string and payment details") and `:id/edit` ("Edit Stringing Order"). Update frontend/src/routes/router.test.tsx.

---

## Phase 4: User Story 2 - Browse and find orders (P1)

### Tests

- [X] T015 [P] [US2] Write selector and API tests in backend/stringing/tests/test_status_counts.py:
  - counts per status with search, payment state and a date range;
  - `status` is ignored;
  - an invalid date gives a 400;
  - 401;
  - exactly 1 query.

  Add a list response-shape assertion for the new fields in backend/stringing/tests/test_api.py.
- [X] T016 [P] [US2] Write integration tests in frontend/src/features/stringing/StringingOrdersPage.test.tsx:
  - rows render the order number, "Walk-in", string @ tension, the date, the badge and the balance;
  - chips show counts and filter;
  - search, filter, chip and page are kept in the URL;
  - the cancel action is hidden for final orders and without the permission;
  - both empty states;
  - axe.

### Implementation

- [X] T017 [US2] Split `search_orders` into `filter_orders(params, *, with_status=True)` and add `status_counts(params)` (one aggregate) in backend/stringing/selectors.py. Add `StringingStatusCountsView` and the route `orders/status-counts/` (before `orders/<pk>/`) in backend/stringing/views.py and backend/stringing/urls.py. T015 must pass.
- [X] T018 [US2] Build frontend/src/features/stringing/StringingOrdersPage.tsx, laid out like SO Home:
  - `SearchBox`;
  - `FilterMenu` with received-from/to and payment state;
  - New Order;
  - `StatusChips` with counts;
  - `DataTable` with the reference columns and row actions (open details sets `?order=`; cancel goes to `:id/cancel`);
  - `Pagination` with the noun "orders".

  T016 must pass.

---

## Phase 5: User Story 3 - Update progress and hand over (P1)

### Tests

- [X] T019 [P] [US3] Write integration tests in frontend/src/features/stringing/OrderDetailsDialog.test.tsx:
  - stepper and details render, including add-ons, colour and store-bought;
  - the dropdown offers only allowed moves;
  - Save Status sends `expected_status`;
  - a conflict response shows the message and refetches;
  - Completed with a balance is blocked and offers Record Payment;
  - recording a payment updates the balance and shows a toast;
  - final orders are read only;
  - a cancelled order shows the reason, staff, time and materials;
  - the refund action shows only with `sales.process_refund` and a refund due;
  - financial fields show only with the permission;
  - axe.

### Implementation

- [X] T020 [US3] Build frontend/src/features/stringing/StringingPaymentDialog.tsx: a receipt up to the balance, or a refund up to the refund due with a required reason; method and reference; a toast naming the new balance or refund due.
- [X] T021 [US3] Build frontend/src/features/stringing/OrderDetailsDialog.tsx, laid out like SO Details:
  - title with badge, stepper, a two-column details grid, the breakdown box, and the payments list;
  - the "Update status" select;
  - Cancel Order (with the permission, non-final), Edit (non-final), Close and Save Status.

  Host it from `StringingOrdersPage` on `?order=`; closing removes the parameter. Use `invalidateAfterStringing` after every save. Make sure frontend/src/api/errors.ts keeps `current_status` from a 400 response, or read it from the raw response, so conflicts are recognised (research R6). T019 must pass.

---

## Phase 6: User Story 4 - Cancel an order (P2)

### Tests

- [X] T022 [P] [US4] Write service and API tests in backend/stringing/tests/test_workflow.py and backend/stringing/tests/test_api.py:
  - cancel requires `materials_used`, a 400 without it (data-model.md StringingOrder.materials_used);
  - the value is stored and recorded in the CANCELLED event `changes`;
  - existing cancel tests are updated for the new body.
- [X] T023 [P] [US4] Write integration tests in frontend/src/features/stringing/CancelStringingOrderPage.test.tsx:
  - the summary header;
  - reason and confirmation required;
  - materials choice sent;
  - an already-final order shows a message and returns to the list;
  - success shows Cancelled with the refundable amount;
  - Back;
  - axe.

### Implementation

- [X] T024 [US4] Add `materials_used` to `cancel_stringing_order` in backend/stringing/services.py, and to `CancelSerializer`/`StringingOrderCancelView` in backend/stringing/serializers.py and backend/stringing/views.py. T022 must pass.
- [X] T025 [US4] Build frontend/src/features/stringing/CancelStringingOrderPage.tsx, laid out like Cancel SO:
  - the summary card;
  - `TextAreaField` for the reason;
  - the materials radio (default "No materials used yet");
  - the audit `Banner`;
  - `ConfirmCheck`;
  - Back and Confirm Cancellation (`danger-confirm`).

  Add the `:id/cancel` child, guarded by `stringing.cancel_stringingorder`, in frontend/src/routes/workAreas.ts. T023 must pass.

---

## Phase 7: Polish & Cross-Cutting

- [X] T026 [P] Add `gross_add_ons` to `revenue_report` and `RevenueReportSerializer` in backend/stringing/selectors.py and backend/stringing/serializers.py. Net revenue includes add-ons. Add a test in backend/stringing/tests/test_selectors.py.
- [X] T027 [P] Update the read-only admin in backend/stringing/admin.py to show the new fields.
- [X] T028 Run the full checks from quickstart.md (backend tests, ruff, `makemigrations --check`, frontend lint, typecheck, tests and build), and fix any failures.
- [ ] T029 Walk through the quickstart.md manual scenarios against the reference PNGs and note any deviations in the spec's adaptation table.

---

## Dependencies

- Setup (T001–T002) comes before Foundational (T003–T009), which comes before the user stories.
- US1 (T010–T014) is the MVP. It provides the routes and the list stub that the later stories plug into.
- US2 (T015–T018) can start after Foundational. T014 needs `StringingOrdersPage`, so create a minimal page in T014 and complete it in T018.
- US3 (T019–T021) depends on US2's page, because it hosts the dialog.
- US4 (T022–T025) needs only Foundational on the backend. Its frontend entry points live in the US2 and US3 screens, but its page and route are independent.
- Polish comes last.

## Parallel examples

- Foundational: T003 ∥ T004. Then T005→T006→T007 (backend) ∥ T008→T009 (frontend).
- US1: T010 ∥ T011. Then T012 (backend) ∥ T013 (frontend).
- US2: T015 ∥ T016. Then T017 ∥ T018.
- US4: T022 ∥ T023. Then T024 ∥ T025.

## Implementation strategy

1. **MVP**: Setup, Foundational, then US1. Staff can take in rackets with add-ons and a deposit.
2. Add US2 (find orders), then US3 (progress and pickup). These complete the daily flow.
3. Add US4 (cancellation), then Polish.
4. Run the full quickstart checks before review. Then `/code-review` and `/security-review`, per CLAUDE.md.
