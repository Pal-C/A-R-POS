# Implementation Plan: Sales Screens

**Branch**: `006-sales-ui` | **Date**: 2026-11-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-sales-ui/spec.md`

## Summary

This feature builds the Sales area using the 005 design system: the list, Create Sale (also used
for draft editing), Sale details, and Cancel Sale.

**Backend additions**, all in `sales`:

- **One-step checkout**: create, finalize and pay in one transaction, made idempotent by
  `client_transaction_id` ([R1](research.md#r1-one-step-checkout-fr-004-sc-003-sc-004)).
- **Replace a draft's cart** in one call ([R2](research.md#r2-drafts-fr-010)).
- **`sale_date`**, with backdating gated by permission
  ([R3](research.md#r3-date-of-sale-and-backdating-fr-005-fr-005a)).
- **An append-only `SaleEvent` history**, with customer linking on finalized sales
  ([R4](research.md#r4-sale-history-fr-009-fr-005a)).
- **List summaries** (products, payment methods) without extra queries per row
  ([R5](research.md#r5-list-data-without-extra-queries-per-row-fr-002)).
- **Cost hidden** from sale lines for staff without the permission
  ([R6](research.md#r6-cost-visibility-in-sales-fr-012)).

**Frontend**: `src/features/sales/` contains:

- a pure cart reducer with string-based money arithmetic
  ([R7](research.md#r7-client-side-money-arithmetic-fr-006));
- the product picker, customer picker, cart and payment components;
- the four screens and two dialogs ([R8](research.md#r8-frontend-structure)).

## Technical Context

**Language/Version**: as in 005. TypeScript ~6.0 strict, React 19.3. Python 3.15, Django 6.1,
DRF 3.18.

**Primary Dependencies**: no new runtime or development dependencies on either side.

**Storage**: PostgreSQL. Three `sales` migrations: the schema, a backfill, and a constraint.

**Testing**: Django `TestCase`, `APITestCase` and `TransactionTestCase` (concurrency), with
query-count assertions. Vitest + Testing Library + MSW + axe.

**Target Platform / Project Type**: as in 005; a web application.

**Performance Goals**:

- Checkout ≤ 500 ms at the 95th percentile (constitution budget).
- One round trip instead of three, with a fixed number of queries for each line.
- List: 4 queries. Detail: a fixed number.
- Cart updates are client-side and take under 100 ms.

**Checkout-path impact (Principle IV)**: lower latency than the existing three-call flow.
Product rows are locked in primary-key order for the length of one transaction only.

**Constraints**:

- Money as strings everywhere, with BigInt cents on the client.
- Append-only history.
- No float arithmetic.
- No browser `confirm` dialogs.

**Scale/Scope**:

- 4 screens, 2 dialogs and about 6 feature components.
- 3 new endpoints, 2 changed serializers, 2 new services plus a refactor of `finalize_sale`.
- 1 new model.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Layering** | ✅ | `checkout_sale`, `replace_draft_cart` and `change_sale_customer` are in `sales/services.py` and reuse `create_draft_sale`, `finalize_sale` and `record_payment`. Views stay thin. |
| I. Transactions and locks | ✅ | Each service runs in a single `transaction.atomic`. Products are locked in primary-key order, and the sale row is locked for draft replacement and customer changes. |
| I. Explicit state | ✅ | Status checks are done in the services. `SaleEvent.Action` uses TextChoices. |
| **II. Testing** | ✅ | See the [contract tests](contracts/sales-api.md#required-tests): services (success and every rejection), API (401/403/400/success, cost hidden), migrations, concurrency (the last unit), and query counts. Frontend: unit tests for the cart reducer and the money library, integration tests for all four screens and both dialogs, an end-to-end checkout flow test, and axe checks. |
| **III. UX consistency** | ✅ | Only shared 005 components, formatters and badges are used. Every view has loading, empty, error and success states. Cancel needs a reason and a confirmation tick. Every money change ends with a toast. The flow is fully keyboard-operable. |
| **IV. Performance** | ✅ | Checkout is a single round trip with asserted query counts. The list prefetches. The new index is on `sale_date`. |
| **Append-only / money / constraints / migrations** | ✅ | `SaleEvent` can't be updated or deleted. Money is Decimal on the server and strings or BigInt on the client. New constraints: `sale_date` required on finalized sales, and an event reason is required. Migrations go schema, backfill, then constraint. |
| **Security** | ✅ | New `sales.backdate_sale` permission. Payment needs `sales.record_payment`, and cancel needs `sales.cancel_sale`, both as before. Cost is hidden from sales responses. Customer usability is checked. |
| **New dependencies** | ✅ | None. |

**Gate result**: PASS before research, and PASS again after design.

**Follow-ups** (pre-existing, outside this scope; recorded by T028):

- The `finalize_sale` and `apply_sale_discount` permissions are defined but not enforced.
- The customer sales history orders by `finalized_at`, not `sale_date`.
- The service-error handler (`handle_service_validation_error`) now keeps field-keyed errors
  (`{"items": [...]}`) instead of flattening them to a list. Existing clients only show
  messages, so this is compatible.
- Line-level discounts exist in the backend but aren't offered in the UI; only the sale-level
  discount is (spec assumption).

## Project Structure

### Documentation (this feature)

```text
specs/006-sales-ui/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/sales-api.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/sales/
├── models.py              # Sale.sale_date (+permission, index, constraint), SaleEvent
├── migrations/0006–0008   # schema, backfill, constraint
├── services.py            # checkout_sale, replace_draft_cart, change_sale_customer; finalize sets sale_date
├── serializers.py         # list summaries, sale_date, events, cost gating; Checkout/DraftCart/CustomerChange serializers
├── views.py               # CheckoutView, DraftCartView, SaleCustomerView; request in serializer context; list prefetch/order
├── urls.py                # checkout/, <pk>/draft/, <pk>/customer/
├── admin.py               # SaleEvent read-only
└── tests/                 # test_checkout.py, test_sale_events.py, test_sale_date_migration.py, test_sales_ui_api.py

frontend/src/
├── lib/money.ts                      # BigInt-cent arithmetic
├── api/sales.ts                      # checkout, replaceDraft, changeCustomer; new fields
├── features/sales/
│   ├── SalesPage.tsx                 # list
│   ├── SaleEditorPage.tsx            # create + draft edit (cart, pickers, payment, date)
│   ├── SaleDetailPage.tsx            # details, payments, history, actions
│   ├── CancelSalePage.tsx
│   ├── cartReducer.ts  cartTotals.ts
│   ├── ProductPicker.tsx  ProductCard.tsx  Cart.tsx  CustomerPicker.tsx  PaymentFields.tsx  SaleSummary.tsx
│   ├── RecordPaymentDialog.tsx  AssociateCustomerDialog.tsx  LeaveGuard.tsx
│   ├── hooks.ts
│   └── *.test.ts(x)
├── routes/workAreas.ts               # Sales area → real pages + children (new, :id, :id/cancel)
└── styles/components/_sales.scss     # product grid, cart panel (tokens only)
```

**Structure Decision**: the same web-app layout as 005. Backend changes stay inside `sales`;
it only reads `catalog.serializers.can_view_cost` and `customers.services.ensure_usable`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| A new checkout endpoint alongside the existing create, finalize and pay endpoints | Completing a sale must be atomic and idempotent (FR-004, SC-004) | Chaining three calls from the client can leave orphaned drafts or unpaid finalized sales when a later call fails |
| `SaleEvent` repeats the event-table pattern | Each app owns its audit trail (as in 002, 003 and 005) | A generic audit table would need generic foreign keys and migrating the existing tables |
