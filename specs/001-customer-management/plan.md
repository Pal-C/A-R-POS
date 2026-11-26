# Implementation Plan: Customer Management

**Branch**: `001-customer-management` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-customer-management/spec.md`

## Summary

Give staff a customer API in the existing `customers` Django app. It covers:

- create, list, details and edit;
- search by name or by phone in any format;
- per-customer history of sales, stringing orders and pre-orders, with a summary of total spent and
  outstanding balance;
- archive and reactivate;
- permanent deletion only for customers with no history.

**Technical approach**:

- **Business rules** live in `customers/services.py`. Read queries and summary totals live in
  `customers/selectors.py`.
- **Totals reuse the sales net-paid rule.** It moves into a shared `sales/selectors.py`, so the
  sales app and customer summaries compute "amount paid" the same way
  ([research R3](research.md#r3-history-summary-totals-reusing-sales-payment-rules)).
- **Phone search** uses a stored, indexed digits-only column
  ([R1](research.md#r1-phone-number-search-and-normalization)).
- **Archive, reactivate and delete** write to a new append-only `CustomerAuditEvent` table
  ([R5](research.md#r5-archive-reactivate-and-delete-audit-trail)).
- **Deletion** is checked under a row lock, backed by changing `Sale.customer` and
  `StringingOrder.customer` to `PROTECT`
  ([R6](research.md#r6-safe-deletion-fr-019-fr-019a-delete-race-edge-case)).
- **Backend only.** Customer screens follow as a separate frontend feature
  ([R10](research.md#r10-frontend-scope)).

## Technical Context

**Language/Version**: Python 3.15 (backend `.venv`), Django 6.1, Django REST Framework 3.18

**Primary Dependencies**: Django, Django REST Framework, django-filter (existing). No new
dependencies.

**Storage**: PostgreSQL (docker-compose `db` service)

**Testing**: Django test runner (`manage.py test`), using `APITestCase` and `TestCase`, with
`CaptureQueriesContext` for query budgets

**Target Platform**: Linux/macOS server; API used by the React (Vite) frontend at
`localhost:5173`

**Project Type**: Web application (Django REST backend + React frontend); this feature touches the
backend only

**Performance Goals**:

- Customer search: ≤ 300 ms p95 at 20k customers (SC-002 asks for 1 s; the constitution's 300 ms is
  stricter).
- Detail + summary: ≤ 300 ms p95 for customers with 500+ transactions (SC-004 asks for 2 s).
- Phone-match lookup: ≤ 200 ms.
- **Checkout-path impact** (constitution Principle IV): `create_draft_sale`, `update_draft_sale` and
  `finalize_sale` call `customers.services.ensure_usable`.
  - The sale's customer is already loaded on these paths, so the check is an attribute read:
    0 extra queries, or at most 1 if the customer is not already loaded.
  - The 500 ms finalize budget is unchanged. A query-count assertion on `finalize_sale` in T036
    guards this.
- `Sale.customer` → `PROTECT` changes delete behaviour only, not reads or writes on the checkout
  path.

**Constraints**:

- Query counts must not grow with customers or transactions (asserted in tests).
- No history may be removed or altered.
- All money values use `Decimal`.

**Scale/Scope**:

- Data: up to about 20k customers; a single customer with up to a few thousand transactions.
- Code: 11 endpoints, 1 new model, 1 extended model, 2 foreign-key behavior changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Code Quality**: rules in `services.py`, thin views | ✅ | Create, update, archive, reactivate, delete and `ensure_usable` live in `customers/services.py`; reads live in `customers/selectors.py`; views only parse, check permissions, call and serialize. |
| I. Transactions and locks | ✅ | Archive, reactivate and delete use `transaction.atomic` with `select_for_update()` on the customer row. |
| I. Explicit state | ✅ | Archive and reactivate are dedicated services that check the current state ([data model](data-model.md#state-transitions)); `CustomerAuditEvent.action` uses `TextChoices`. |
| I. Static checks | ✅ | ruff must pass; there is no frontend code in this feature. |
| I. Cross-app writes via services | ✅ | Customers only **reads** sales, stringing and pre-order data. The sales services call `customers.services.ensure_usable`. |
| **II. Testing Standards** | ✅ | Service tests for every rule; API tests for 401/403/400/404 and success; constraint tests (blank name); a concurrency-sensitive delete-race test; query-count tests; a workflow test ([quickstart](quickstart.md#automated-validation)). |
| **III. UX Consistency** | ✅ (API scope) | Consistent Django REST Framework error shapes, with field-keyed messages that can be shown to staff. Loading, empty and error UI states are deferred to the frontend feature ([R10](research.md#r10-frontend-scope)). The contract supplies the data for every state, including empty lists. Domain terms match the existing apps. |
| **IV. Performance** | ✅ | Pagination on all lists; `select_related` and subquery annotations for history; summary in a fixed number of aggregate queries; new indexes `phone_normalized` and `(is_active, full_name)`; locks held only inside short atomic blocks. |
| **Append-only history** | ✅ | Archiving never modifies transactions; the audit table is append-only; deletion is only possible when there is no history. Fixes the existing `SET_NULL` violations on `Sale.customer` and `StringingOrder.customer`. |
| **Money as Decimal** | ✅ | All totals use Decimal fields and database `Sum`/`F` expressions with `DecimalField` output. |
| **Database constraints** | ✅ | New `customer_full_name_not_blank` check constraint; foreign-key `PROTECT` backs the delete rule. |
| **Migrations** | ✅ | New migrations only; no applied migration is rewritten. Includes a backfill data migration. |
| **Security**: authentication by default, permissions for sensitive operations | ✅ | `IsAuthenticated` on all endpoints; `customers.archive_customer` for archive and reactivate; `customers.delete_customer` for delete. |
| **Security**: personal data only to roles that need it | ✅ | Every current staff role serves customers at the counter, so every role needs contact details to look up, contact and serve them (spec Assumptions, "Who can do what"). The rule is therefore met by allowing all signed-in staff. Cost data is not exposed by any customer endpoint. **Re-check trigger**: when a role that does not serve customers is introduced (e.g. stock-only staff), gate customer endpoints with `customers.view_customer`. |
| **New dependencies justified** | ✅ | None added (phone library and `pg_trgm` considered and rejected, see R1 and R2). |

**Gate result (pre-research)**: PASS.

**Gate result (post-design re-check)**: PASS.

- The design artifacts add no unlisted dependencies.
- Every endpoint in the [contract](contracts/customers-api.md) has a permission and budget row.
- Every validation rule in the [data model](data-model.md#validation-summary-spec--rule) maps to a
  service, a constraint, or both.
- Two justified deviations are listed under Complexity Tracking.
- Re-checked after `/speckit-analyze`. Fixed: screen states added to the spec (C1); unauthenticated
  tests for every endpoint (C2); checkout-path impact stated (C3); personal-data rationale made
  explicit (D1).

## Project Structure

### Documentation (this feature)

```text
specs/001-customer-management/
├── plan.md               # This file
├── research.md           # Phase 0: decisions R1–R10
├── data-model.md         # Phase 1: Customer, CustomerAuditEvent, derived summary
├── quickstart.md         # Phase 1: validation guide
├── contracts/
│   └── customers-api.md  # Phase 1: REST contract
├── checklists/
│   └── requirements.md   # Spec quality checklist
└── tasks.md              # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
backend/
├── config/
│   └── urls.py                      # + path("api/customers/", include("customers.urls"))
├── customers/
│   ├── models.py                    # Customer (+phone_normalized, constraint, permission), CustomerAuditEvent
│   ├── phone.py                     # NEW: normalize_phone(), is_phone_query()
│   ├── services.py                  # NEW: create/update/archive/reactivate/delete_customer, ensure_usable
│   ├── selectors.py                 # NEW: search, phone_matches, customer_summary, history querysets
│   ├── serializers.py               # NEW: list/detail/write/summary/history serializers
│   ├── views.py                     # list/create, detail/update/delete, archive, reactivate, history, phone-matches
│   ├── urls.py                      # NEW
│   ├── admin.py                     # Customer + CustomerAuditEvent (read-only) admin
│   ├── migrations/                  # 0002 schema, 0003 backfill phone_normalized
│   └── tests/                       # NEW package (replaces empty tests.py)
│       ├── test_phone.py
│       ├── test_services.py
│       ├── test_selectors.py
│       ├── test_api.py
│       └── test_workflow.py
├── sales/
│   ├── selectors.py                 # NEW: net_paid_expression(), net_paid_subquery()
│   ├── models.py                    # Sale.customer on_delete → PROTECT
│   ├── services.py                  # call customers.services.ensure_usable (create, update, finalize)
│   └── migrations/                  # 0004 customer PROTECT
├── stringing/
│   ├── models.py                    # StringingOrder.customer on_delete → PROTECT
│   ├── admin.py                     # form validation: archived customer not newly assignable
│   └── migrations/                  # 0002 customer PROTECT
└── preorders/
    └── admin.py                     # form validation: archived customer not newly assignable
```

**Structure Decision**: the existing Django web-app layout (`backend/` Django project with one app
per bounded context, plus `frontend/`). All new code goes in `backend/customers/`, with small,
listed touch points in `sales`, `stringing` and `preorders`. `customers/tests.py` becomes a
`tests/` package, matching `sales/` and `inventory/` and fixing the test discovery clash.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `Customer.save()` sets `phone_normalized` (logic in the model, not a service), against Principle I layering | The column is derived data that must stay correct on **every** write path, including Django admin and shell, which bypass services. Otherwise search silently misses customers. | Setting it only in `services.py` leaves admin edits with a stale value. A database trigger is harder to test and to see in Django. |
| FR-017 enforced for stringing orders and pre-orders only through Django admin forms | Those apps have no services or API yet, and admin is their only create path. Building them is out of scope. | Building stringing and pre-order create services now would greatly expand the feature. `limit_choices_to` would block editing existing orders whose customer was later archived. |
