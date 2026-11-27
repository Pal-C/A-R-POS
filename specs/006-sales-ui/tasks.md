---
description: "Task list for Sales Screens"
---

# Tasks: Sales Screens

**Input**: Design documents from `/specs/006-sales-ui/`

**Tests**: Required (constitution II; spec SC-003/SC-004/SC-005). Write tests first and see them fail.

**Organization**: US1 is ring up a sale, US2 browse sales, US3 view/collect/associate, US4 cancel.

---

## Phase 1: Setup

- [X] T001 Create frontend/src/features/sales/ and frontend/src/styles/components/_sales.scss. Import the partial in frontend/src/styles/main.scss.

---

## Phase 2: Foundational (blocks all stories)

### Tests first

- [X] T002 [P] Write model and migration tests in backend/sales/tests/test_sale_events.py and backend/sales/tests/test_sale_date_migration.py:
  - the `saleevent_reason_required` constraint (data-model.md SaleEvent.reason);
  - PROTECT on `sale` and `performed_by`;
  - the `sale_date_required_when_finalized` constraint (data-model.md Sale.sale_date);
  - the backfill sets the Asia/Manila local date of `finalized_at`, using a migration test in the style of the existing test_migrations.py.
- [X] T003 [P] Write unit tests in frontend/src/lib/money.test.ts:
  - `toCents` and `fromCents` round-trip;
  - add, subtract and multiply, including 0.10 + 0.20 = 0.30;
  - large amounts;
  - compare.

### Implementation

- [X] T004 Make the model changes in backend/sales/models.py:
  - `Sale.sale_date`, the `backdate_sale` permission and the `(-sale_date, -created_at)` index;
  - the `SaleEvent` model (data-model.md SaleEvent.*).

  Generate backend/sales/migrations/0006_sale_sale_date_saleevent.py, write the data migration 0007_backfill_sale_date.py, then generate 0008_sale_date_constraint.py. Register `SaleEvent` as read-only in backend/sales/admin.py. T002 must pass.
- [X] T005 [P] Implement frontend/src/lib/money.ts (research R7). T003 must pass.
- [X] T006 Update frontend/src/api/sales.ts:
  - add `sale_date`, `items_summary`, `payment_methods` and `events` to the types;
  - make `unit_cost_price` and `gross_profit` optional;
  - add `checkout(body)`, `replaceDraft(id, body)` and `changeCustomer(id, body)`, with types from contracts/sales-api.md.

  Add the matching cases to frontend/src/api/domain.test.ts.

---

## Phase 3: User Story 1 - Ring up a sale (P1) 🎯 MVP

### Tests

- [X] T007 [P] [US1] Write service tests in backend/sales/tests/test_checkout.py:
  - checkout with no payment, partial payment and full payment, checking the status, `sale_date` and stock;
  - an idempotent repeat by `client_transaction_id` returns the same sale and creates no second one;
  - checkout from a draft;
  - a stock shortage rolls back (no sale, stock unchanged);
  - an inactive product;
  - an empty or duplicate item list;
  - a discount or payment over the total;
  - a future date;
  - a past date without a reason, and without the permission;
  - a backdate writes a BACKDATED event;
  - a payment without `sales.record_payment` is refused;
  - an archived customer.

  Also check that existing `finalize_sale` callers get `sale_date` set.
- [X] T008 [P] [US1] Write a concurrency test in backend/sales/tests/test_checkout.py (`TransactionTestCase`): two checkouts compete for the last unit; one gets 201 and the other a ValidationError, with stock at 0.
- [X] T009 [P] [US1] Write API tests in backend/sales/tests/test_sales_ui_api.py for `POST /checkout/` and `PUT /{id}/draft/`:
  - 401, 403 and 400 shapes, including the `items` stock message;
  - 201 vs 200 on an idempotent repeat;
  - the checkout query count;
  - the cost fields are absent without `catalog.view_product_cost` and present with it, on checkout, detail and draft responses.
- [X] T010 [P] [US1] Write unit tests in frontend/src/features/sales/cartReducer.test.ts:
  - add merges lines and caps at the available stock;
  - `setQuantity` bounds;
  - remove;
  - discount and payment;
  - load a draft;
  - reset regenerates the `clientTransactionId`;
  - `cartTotals` (subtotal, total, balance) as Money strings;
  - the validation rules (data-model.md "Validation").
- [X] T011 [P] [US1] Write integration tests in frontend/src/features/sales/SaleEditorPage.test.tsx (msw):
  - product search and Add update the cart and totals;
  - a sold-out product's Add is disabled;
  - customer search, link, and inline create;
  - the discount and payment validation;
  - completing sends the exact checkout body and reuses the same `client_transaction_id` on retry after a network error;
  - a success toast with the number and balance, then navigation to the sale;
  - a stock-shortage error keeps the cart and names the product;
  - no payment fields without `sales.record_payment`;
  - the date is read-only without `sales.backdate_sale`;
  - backdating needs a reason, a future date is blocked, and "Set to today" works;
  - Save Draft;
  - the leave guard;
  - keyboard-only completion;
  - an axe check.

### Implementation

- [X] T012 [US1] Implement backend/sales/services.py:
  - `finalize_sale` sets `sale_date` (today, local);
  - `checkout_sale` and `replace_draft_cart` (research R1–R3, data-model.md "Service rules"). Each has a docstring stating its side effects and runs in `transaction.atomic`.

  T007 and T008 must pass.
- [X] T013 [US1] In backend/sales/serializers.py:
  - add `CheckoutSerializer` and `DraftCartSerializer`;
  - add `sale_date` and `events` to `SaleDetailSerializer`;
  - gate cost in `SaleItemSerializer` (R6).

  In backend/sales/views.py:
  - add `CheckoutView` and `DraftCartView`;
  - pass the request into every serializer context (`sale_detail_response(request, …)`).

  Add the routes to backend/sales/urls.py. T009 must pass, and existing sales and customers tests still pass.
- [X] T014 [P] [US1] Implement frontend/src/features/sales/cartReducer.ts and cartTotals.ts. T010 must pass.
- [X] T015 [P] [US1] Implement frontend/src/features/sales/ProductCard.tsx and ProductPicker.tsx (debounced search over active products, paginated grid in a navy panel, stock-aware Add), plus their styles in _sales.scss.
- [X] T016 [P] [US1] Implement frontend/src/features/sales/CustomerPicker.tsx (search by name or phone via `customersApi.list`, choose, clear to walk-in, inline create via `customersApi.create`), PaymentFields.tsx and Cart.tsx (lines with a quantity stepper, remove, and a totals panel).
- [X] T017 [US1] Implement frontend/src/features/sales/SaleEditorPage.tsx (`/sales/new`, and drafts at `/sales/:id`): the reference layout, date with "Set to today" and backdate reason, Complete Sale and Save Draft mutations, error mapping (with `splitApiError`), toasts, and LeaveGuard.tsx (`useBlocker` + Modal). Also hooks.ts. Register the Sales area children in frontend/src/routes/workAreas.ts. T011 must pass.

**Checkpoint**: quickstart scenarios 1–7 pass.

---

## Phase 4: User Story 2 - Browse sales (P1)

- [X] T018 [P] [US2] Write API tests in backend/sales/tests/test_sales_ui_api.py:
  - the list has `items_summary`, `payment_methods` (distinct posted receipts, refunds excluded) and `sale_date`;
  - the order is by `sale_date` descending with drafts first;
  - search and status filter;
  - 4 queries regardless of the number of rows.
- [X] T019 [P] [US2] Write integration tests in frontend/src/features/sales/SalesPage.test.tsx:
  - the columns, products truncated with a title, methods joined or "—", the date, and status badges;
  - search and status filter update the request and the URL;
  - pagination;
  - empty states;
  - error state;
  - the row opens the sale;
  - CREATE SALE goes to /sales/new;
  - an axe check.
- [X] T020 [US2] Add `items_summary`, `payment_methods` and `sale_date` to `SaleListSerializer`, and add the list prefetch and ordering in backend/sales/views.py. T018 must pass.
- [X] T021 [US2] Implement frontend/src/features/sales/SalesPage.tsx (toolbar: search, status filter, CREATE SALE; DataTable; Pagination) and register it as the Sales area page. T019 must pass.

---

## Phase 5: User Story 3 - View, collect, associate (P2)

- [X] T022 [P] [US3] Write service and API tests in backend/sales/tests/test_sale_events.py and test_sales_ui_api.py for `change_sale_customer` and `POST /{id}/customer/`:
  - draft, cancelled, archived, unchanged and blank-reason cases are rejected;
  - a CUSTOMER_CHANGED event is written with old and new IDs;
  - the detail includes events;
  - 401 and 404.
- [X] T023 [P] [US3] Write integration tests in frontend/src/features/sales/SaleDetailPage.test.tsx:
  - details, totals, payments, events and the walk-in notice render;
  - a draft redirects to the editor layout;
  - Record payment validates against the balance, then updates the status with a toast;
  - Associate customer requires a reason and refreshes;
  - actions are hidden without permission;
  - an axe check.
- [X] T024 [US3] Implement `change_sale_customer` in backend/sales/services.py, `SaleCustomerChangeSerializer`, `SaleCustomerView` and its route. T022 must pass.
- [X] T025 [US3] Implement frontend/src/features/sales/SaleSummary.tsx, SaleDetailPage.tsx, RecordPaymentDialog.tsx (uses `salesApi.recordPayment`) and AssociateCustomerDialog.tsx (uses CustomerPicker plus a reason). T023 must pass.

---

## Phase 6: User Story 4 - Cancel a sale (P2)

- [X] T026 [P] [US4] Write integration tests in frontend/src/features/sales/CancelSalePage.test.tsx:
  - the summary (number, customer, item count, method, date, badge, total);
  - Confirm is disabled until a reason is entered and the box ticked;
  - success returns to the sale with a toast;
  - access is denied without `sales.cancel_sale`;
  - drafts and cancelled sales show "can't be cancelled";
  - an axe check.

  Extend the backend tests: the cancel response hides cost and includes `refund_due`.
- [X] T027 [US4] Implement frontend/src/features/sales/CancelSalePage.tsx (`/sales/:id/cancel`, with permission `sales.cancel_sale`), with the banner "Items are returned to stock. Recorded as cancelled by <name> on <date>…". T026 must pass.

---

## Phase 7: Polish

- [X] T028 [P] Update frontend/README.md (`lib/money.ts` and sales feature notes) and record the follow-ups in plan.md.
- [X] T029 Run all checks:
  - backend: tests, ruff, `makemigrations --check`, and ruff format on new files;
  - frontend: lint, typecheck, test, build, and the bundle budget;
  - no hex colors outside the tokens file.
- [X] T030 Visually review against the Figma PNGs on a throwaway `testserver` database (quickstart 13). Record the differences and fix any styling bugs.
  - 2026-11-28: walked through Create Sale (customer link, cart, ₱40 discount, partial ₱300 cash payment), Sale Details, the Sales list and Cancel Sale at about 950 px and 1440 px on a throwaway database. All screens match the references. Fixed: a stray vertical scrollbar on tables, the "+" icon on sold-out cards, the sale number wrapping in the list, and the "Draft Draft" wording. Intentional differences: Create Sale shows one customer search box with a New customer action instead of separate Name and Contact fields; a Save Draft action is added; cancelling has no inventory-handling choice (deferred); the edit-with-correction screen for finalized sales is replaced by the read-only Sale Details plus Associate customer (Q1).

---

## Phase 8: Review Fixes (from /code-review, 2026-11-28)

- [X] T031 Reopened drafts load current stock and prices for their products (`DraftEditor` in SaleDetailPage.tsx, plus `loadDraft` with `current` in cartReducer.ts). Quantities can increase up to the current stock. Products no longer sold block completion. A banner lists price changes since the draft was saved.
- [X] T032 Keep line discounts: `CartLineSerializer.discount_amount` on the backend; the cart carries, shows and re-sends line discounts; totals include them.
- [X] T033 Checkout with an unknown `draft_id` returns 400 `{"draft_id": ...}`, not 500.
- [X] T034 `client_transaction_id` only matches a finalized sale by the same user. Any other reuse returns 400.
- [X] T035 Work out "today" when Complete Sale is pressed; a default date from the previous day rolls over to the new day.
- [X] T036 Track unsaved changes against the last saved cart, so the leave warning still works after Save Draft on an existing draft.
- [X] T037 Never show a negative cart total.
- [X] T038 `saleTitle` makes titles read "Sale #S…" for finalized sales (as in the references) and "Draft #id" for drafts.
- [X] T039 The list index `sale_date_list_idx` matches the list ordering `(-sale_date, -created_at, -id)`, folded into migration 0006 because it was never released.

---

## Dependencies & Execution Order

- Setup comes first, then Foundational (T002–T006), which blocks all stories.
- US1 (T007–T017) is the MVP. US2 can run in parallel with US1 after Foundational (it touches different files except workAreas.ts, which goes last).
- US3 depends on US1 (it reuses CustomerPicker and the editor for drafts).
- US4 depends on US3 (the detail page links to it).
- Polish comes last.

## Implementation Strategy

1. MVP: Foundational and US1 (ring up sales).
2. US2: the list.
3. US3: details, collecting and associating.
4. US4: cancel.
5. Polish, then `/code-review` and `/security-review`.
