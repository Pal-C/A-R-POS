# Implementation Plan: Stringing Management

**Branch**: `002-stringing-management` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-stringing-management/spec.md`

## Summary

Give staff a stringing-order API in the existing `stringing` Django app. It covers:

- intake with unique order numbers;
- edits;
- a one-step-at-a-time status workflow (pickup only when paid in full);
- partial and full payments and refunds;
- cancellation with a reason;
- a full audit history;
- search and filters;
- a revenue and profit report that counts orders once they are paid in full.

**Technical approach**:

- **Business rules** live in `stringing/services.py`. Queries and the report live in
  `stringing/selectors.py`. Views stay thin.
- **Order numbers** come from a PostgreSQL sequence: `STR-{year}-{seq:06d}`
  ([R1](research.md#r1-order-number-generation-fr-002-sc-002)).
- **Money stays in the shared `Payment` table.** It is written only by `sales.services.record_payment`
  / `process_refund`. These services now call `stringing.services.sync_payment_state`, which
  maintains a new `paid_in_full_at` date that drives revenue recognition
  ([R2](research.md#r2-where-payments-are-recorded-and-how-paid-in-full-is-tracked-fr-014017-fr-028),
  [R3](research.md#r3-revenue-and-profit-report-fr-026029-q1)).
- **Audit**: a new append-only `StringingOrderEvent` table, merged with payments in the history
  view ([R4](research.md#r4-status-transitions-and-audit-trail-fr-010013-fr-021025)).
- **Permissions**: the broken `Meta.permissions` is fixed, adding cancel and financials permissions.
  Receipts on the generic payments endpoint now require `sales.record_payment`
  ([R6](research.md#r6-permissions-fr-030)).
- **Backend only** ([R9](research.md#r9-frontend-scope)).

## Technical Context

**Language/Version**: Python 3.15 (backend `.venv`), Django 6.1, Django REST Framework 3.18

**Primary Dependencies**: Django, Django REST Framework, django-filter (existing). No new
dependencies.

**Storage**: PostgreSQL (docker-compose `db` service). Uses a native sequence.

**Testing**: Django test runner (`manage.py test`) with `TestCase`, `APITestCase` and
`TransactionTestCase` (for concurrency), plus `CaptureQueriesContext` for query budgets.

**Target Platform**: Linux/macOS server; API used by the React (Vite) frontend.

**Project Type**: Web application; this feature touches the backend only.

**Performance Goals**:

- List and search: ≤ 300 ms p95 at 50k orders, with a fixed query count per page.
- Create, edit, status change and payment: ≤ 200 ms.
- Revenue report: ≤ 3 aggregate queries, ≤ 500 ms for a one-month range.
- **Checkout-path impact** (Principle IV): `sales.services.record_payment` gains one branch for
  stringing targets only. Sale payments add 0 queries, and the 500 ms sale-payment budget is
  unchanged. A query-count test on a sale payment guards this. The receipt permission check is an
  in-memory permission lookup (cached per request).

**Constraints**: append-only events and payments; Decimal money; row lock on the order for every
state, money or edit change; no network calls inside locks.

**Scale/Scope**: about 50k orders over the system's life; 10 endpoints, 1 new model, 1 extended
model, 1 DB sequence, a small change to `sales.services`/`sales.views`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Layering** | ✅ | Create, update, change_status, cancel, sync_payment_state and the payment wrapper are in `stringing/services.py`; search, history and report in `stringing/selectors.py`; views parse, check permissions, call and serialize. Payment writes go through `sales.services` (the owning app). |
| I. Transactions and locks | ✅ | Every write service runs in `transaction.atomic`, with `select_for_update()` on the single order row. `record_payment` already locks the order before calling `sync_payment_state`. |
| I. Explicit state | ✅ | `Status` and `StringingOrderEvent.EventType` are `TextChoices`. A transition table plus dedicated `change_status` and `cancel_stringing_order` services check the current state. |
| I. Static checks and size | ✅ | ruff passes. No frontend code. Docstrings on public services state their side effects. |
| **II. Testing** | ✅ | Service tests for every rule and rejection; API tests for 401/403/400/404/success per endpoint; a test per new DB constraint; a concurrency test (parallel creates → unique numbers; parallel receipts never exceed the total); query-count tests (list, detail, sale payment); regression tests for the sales payment permission and sync; an end-to-end workflow test. |
| **III. UX consistency** | ✅ (API scope) | DRF field-keyed errors with human messages; payment and status responses return the updated order for confirmations; terminology matches (Stringing Order, Received/In Progress/Ready for Pickup/Completed/Cancelled). Screen states are deferred to the frontend (R9). |
| **IV. Performance** | ✅ | Paged lists; `select_related(customer, created_by, cancelled_by)` plus a net-paid subquery annotation (no N+1); new indexes on status/created_at and paid_in_full_at; the report uses aggregates only. |
| **Append-only history** | ✅ | No delete endpoint; events and payments are never updated; cancellation is a state change, and refunds are new Payment rows; FKs `PROTECT`. Every write records the user and time. |
| **Money as Decimal** | ✅ | Decimal fields and `Sum`/`F` with `DecimalField` output; JSON changes store money as strings. |
| **DB constraints** | ✅ | Existing amount checks, plus new not-blank, cancel-consistency and completed-time constraints; unique order number backed by a sequence. "Total ≥ paid" spans tables, so it is enforced in the service under a row lock (see Complexity Tracking). |
| **Migrations** | ✅ | New schema migration, a sequence migration (`RunSQL` with reverse), and a backfill data migration. Applied migrations are not edited. |
| **Security** | ✅ | `IsAuthenticated` everywhere; dedicated permissions for cancel, financials, receipts and refunds; cost and profit masked by permission; no new secrets. Fixes the existing receipt-permission gap on `/api/sales/payments/`. |
| **New dependencies** | ✅ | None (audit package rejected in R4). |

**Gate result (pre-research)**: PASS.

**Gate result (post-design re-check)**: PASS. Every endpoint in the
[contract](contracts/stringing-api.md) has a permission, and every rule in the
[data model](data-model.md#validation-summary-spec--rule) maps to a service and/or a constraint.

## Project Structure

### Documentation (this feature)

```text
specs/002-stringing-management/
├── plan.md               # This file
├── research.md           # Phase 0: decisions R1–R9
├── data-model.md         # Phase 1: StringingOrder (extended), StringingOrderEvent
├── quickstart.md         # Phase 1: validation guide
├── contracts/
│   └── stringing-api.md  # Phase 1: REST contract
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── config/
│   ├── settings.py                  # + STORE_TIME_ZONE = "Asia/Manila"
│   └── urls.py                      # + path("api/stringing/", include("stringing.urls"))
├── stringing/
│   ├── models.py                    # StringingOrder (+fields, constraints, indexes, fixed Meta.permissions), StringingOrderEvent
│   ├── migrations/
│   │   ├── 0003_...                 # schema: new fields, event model, constraints, indexes, permissions
│   │   ├── 0004_order_number_seq    # RunSQL CREATE SEQUENCE (start above existing max)
│   │   └── 0005_backfill            # paid_in_full_at / updated_at for existing rows
│   ├── services.py                  # NEW: create/update/change_status/cancel, sync_payment_state, record_order_payment
│   ├── selectors.py                 # NEW: search_orders, order_detail queryset, order_history, revenue_report
│   ├── serializers.py               # NEW: list/detail/write/status/cancel/payment/report serializers, financial masking
│   ├── views.py                     # NEW: thin DRF views
│   ├── urls.py                      # NEW
│   ├── admin.py                     # read-only events inline; disable delete
│   └── tests/                       # NEW: factories, test_models, test_services, test_selectors,
│                                    #      test_api, test_auth, test_concurrency, test_workflow
├── sales/
│   ├── services.py                  # record_payment → sync_payment_state for stringing targets
│   ├── views.py                     # receipts require sales.record_payment
│   └── tests/                       # update for the receipt permission; sale-payment query count
└── customers/tests/factories.py     # make_stringing_order uses the stringing factory/sequence-safe numbers
```

**Structure Decision**: Web application layout, backend only. All new code lives in the existing
`backend/stringing` app, with two small edits in `backend/sales` and one in `backend/config`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| "Total ≥ amount paid" is enforced in services, not as a DB constraint | Amount paid is derived from the `Payment` table; a CHECK constraint cannot reference another table | Storing a cached `amount_paid` column would allow a CHECK, but it duplicates the shared net-paid rule (customers R3) and creates a second source of truth for money |
| `sales.services.record_payment` calls into `stringing.services` | `paid_in_full_at` must stay correct no matter which endpoint posts the payment | Updating it only from a stringing endpoint would leave it stale for payments posted through `/api/sales/payments/` |
