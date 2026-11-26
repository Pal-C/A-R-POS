# Implementation Plan: Pre-order Management

**Branch**: `003-preorder-management` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-preorder-management/spec.md`

## Summary

This adds a pre-order API to the existing `preorders` Django app. It covers:

- creating pre-orders with unique order numbers, for an active customer and product;
- editing, with rules that depend on the order's status;
- a one-step-at-a-time status workflow;
- marking a product as arrived, either oldest-first or for orders staff pick;
- deposits, payments and refunds;
- fulfillment, which requires full payment;
- cancellation with a reason;
- audit history;
- search and filters, including overdue orders;
- a per-product summary of units waiting.

Pre-orders never touch inventory.

**Technical approach**: the same architecture as feature 002 (stringing).

- **Business rules** live in `preorders/services.py`, and queries in `preorders/selectors.py`.
- **Order numbers** come from a PostgreSQL sequence ([R1](research.md#r1-order-numbers-fr-002)).
- **Money** stays in the shared `Payment` table, written only through the sales services.
  `record_payment` gains one rule: it refuses receipts on FULFILLED pre-orders
  ([R2](research.md#r2-payments-balance-and-settled-orders-fr-012015-fr-016)).
- **Audit history**: a new append-only `PreOrderEvent` table
  ([R6](research.md#r6-audit-trail-fr-025)).
- **Arrival** of a product is a single locked transaction, so either every selected order is
  marked or none is ([R4](research.md#r4-status-workflow-arrival-and-fulfillment-fr-007011-fr-016)).
- **Permissions**: the broken permissions declaration is fixed, adding cancel and price-override
  permissions ([R7](research.md#r7-permissions-fr-026)).
- **Backend only.**

## Technical Context

**Language/Version**: Python 3.15, Django 6.1, Django REST Framework 3.18

**Primary Dependencies**: Django, Django REST Framework, django-filter (all already used). No new
dependencies.

**Storage**: PostgreSQL, including a native sequence for order numbers.

**Testing**: Django test runner (`TestCase`, `APITestCase`, `TransactionTestCase`) and
`CaptureQueriesContext`.

**Target Platform**: Linux/macOS server; the API is used by the React frontend.

**Project Type**: Web application; this feature is backend only.

**Performance Goals**:

- List and search: ≤ 300 ms at 20k pre-orders, with a fixed number of queries per page.
- Product summary: 2 queries.
- Arrival: one transaction that locks only that product's ORDERED rows.
- **Checkout-path impact** (Principle IV): `record_payment` gets one extra in-memory status check
  for pre-order targets only. Sale payments make the same number of queries as before; the existing
  sales query-count test guards this.

**Constraints**:

- Events and payments are append-only.
- Money is stored as Decimal.
- Every status, money or edit change takes a row lock.
- No inventory calls.

**Scale/Scope**:

- About 20k pre-orders.
- 11 endpoints, 1 new model and 1 extended model, 1 sequence.
- Small changes to `sales/services.py` and `customers/selectors.py`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Layering** | ✅ | Create, update, change_status, mark_product_arrived, fulfill, cancel and the payment wrapper are in `preorders/services.py`. Search, history and the summary are in selectors. Views stay thin. Payment writes go through `sales.services`. |
| I. Transactions and locks | ✅ | All writes are atomic. Single-order changes lock that row. Arrival locks the product's ORDERED rows in primary-key order. |
| I. Explicit state | ✅ | TextChoices plus a transition table. Fulfillment and cancellation are dedicated services. |
| I. Static checks | ✅ | ruff passes. |
| **II. Testing** | ✅ | Each service is tested for success and for every rejection. API tests cover 401/403/400/404/success per endpoint. Each new constraint has a test. Concurrency tests cover parallel creates, parallel receipts, and two arrivals competing for the same orders. Query counts are asserted on the list and summary. Regression tests cover sales (fulfilled receipt) and customers (summary). There is an end-to-end workflow test. |
| **III. UX consistency** | ✅ (API scope) | Field-keyed errors. Action responses return the updated record, or the arrival result, so the UI can confirm. Terminology matches: Pre-order, Pending, Ordered from Supplier, Arrived, Fulfilled, Cancelled. |
| **IV. Performance** | ✅ | Pagination; `select_related(customer, product, users)` plus the net-paid subquery; new indexes; aggregate-only summary. |
| **Append-only history** | ✅ | No delete route; the admin is read-only; events and payments are never updated; cancellation is a state change. |
| **Money as Decimal** | ✅ | Decimal fields and Decimal database expressions. |
| **DB constraints** | ✅ | Existing quantity and price checks, plus new cancel and fulfilled consistency checks and a unique number. "Total ≥ paid" is enforced in the service under a lock, as in stringing. |
| **Migrations** | ✅ | Schema migration, then a sequence, then a backfill, then constraints, in that order. |
| **Security** | ✅ | Every endpoint requires authentication. Dedicated permissions for cancel, price override, receipts and refunds. |
| **New dependencies** | ✅ | None. |

**Gate result**: PASS before research, and PASS again after design.

## Project Structure

### Documentation (this feature)

```text
specs/003-preorder-management/
├── plan.md
├── research.md            # R1–R10
├── data-model.md
├── quickstart.md
├── contracts/preorders-api.md
├── checklists/requirements.md
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── config/urls.py                   # + path("api/preorders/", include("preorders.urls"))
├── preorders/
│   ├── models.py                    # PreOrder (+fields, constraints, indexes, fixed permissions), PreOrderEvent
│   ├── migrations/0002–0005         # schema, sequence, backfill, constraints
│   ├── services.py                  # NEW
│   ├── selectors.py                 # NEW
│   ├── serializers.py               # NEW
│   ├── views.py                     # NEW (replaces placeholder)
│   ├── urls.py                      # NEW
│   ├── admin.py                     # read-only + events inline
│   └── tests/                       # NEW: factories, models, services, selectors, api, auth, concurrency, workflow
├── sales/services.py                # refuse receipts on FULFILLED pre-orders
└── customers/
    ├── selectors.py                 # FULFILLED pre-orders settled in the summary
    └── tests/factories.py           # make_preorder delegates to the preorders factory
```

**Structure Decision**: web application, backend only. All new code goes in `backend/preorders`,
with small edits in `sales`, `customers` and `config`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| "Total ≥ amount paid" is enforced in the service, not as a DB constraint | Amount paid comes from the Payment table, and a CHECK constraint can't look at another table | A cached amount-paid column would mean storing money in two places (same reasoning as stringing) |
| `PreOrderEvent` duplicates the shape of `StringingOrderEvent` | Each app owns its own audit trail | A shared generic event table would mean migrating stringing data and adding generic foreign keys; that's more risk than one small model |
