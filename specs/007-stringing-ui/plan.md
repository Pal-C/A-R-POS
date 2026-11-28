# Implementation Plan: Stringing Order Screens

**Branch**: `007-stringing-ui` | **Date**: 2026-11-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-stringing-ui/spec.md`

## Summary

This feature replaces the Services placeholder with the Stringing Orders area, built on the 005
design system and the 006 patterns. It adds four screens: the list with status chips, the
Details dialog, Create/Edit, and Cancel.

**Backend additions**, all in `stringing`:

- **Add-on, colour and store-bought fields**, with the total formula changed to include
  add-ons ([R1](research.md#r1-add-ons-colour-and-store-bought-string-fr-021)).
- **Create with an optional deposit**, atomic and idempotent through `client_transaction_id`
  ([R3](research.md#r3-create-with-deposit-in-one-idempotent-step-fr-009-us1-as6as7)).
- **`materials_used`** stored on cancellation
  ([R4](research.md#r4-materials-used-on-cancellation-fr-022)).
- **A one-query status-counts endpoint** for the chips
  ([R5](research.md#r5-status-chip-counts-fr-002)).
- **The revenue report** includes add-ons.

**Frontend**: a new `src/features/stringing/` folder containing:

- a pure form model for totals and validation, using BigInt cents;
- an Invoice panel;
- the four screens and a payment/refund dialog.

`CustomerPicker`, `LeaveGuard` and the payment-method list move to shared locations so Sales
and Services both use them ([R8](research.md#r8-frontend-structure-and-reuse)). Default prices
come from `config.ts` ([R2](research.md#r2-shop-default-prices-fr-020)).

## Technical Context

**Language/Version**: as in 005 and 006: TypeScript ~6.0 strict, React 19.3, Python 3.15,
Django 6.1, DRF 3.18.

**Primary Dependencies**: no new runtime or development dependencies.

**Storage**: PostgreSQL. One `stringing` migration (fields with safe defaults, plus constraints).

**Testing**: Django `TestCase`, `APITestCase` and `TransactionTestCase` (concurrent idempotent
create), with query-count assertions. Vitest + Testing Library + MSW + axe.

**Target Platform / Project Type**: web application (Django API + React SPA).

**Performance Goals**:

- List ≤ 300 ms at the 95th percentile, with an unchanged query count.
- Status counts: 1 query.
- Create with deposit: one round trip and a fixed number of queries.
- Invoice updates are client-side, under 100 ms.

**Checkout-path impact (Principle IV)**: none. Sales checkout is untouched. The stringing create
path gains one payment insert inside the same transaction.

**Constraints**:

- Money as strings, with BigInt cents on the client.
- Append-only events.
- No browser `confirm` dialogs.
- Financial fields stay hidden without the permission.

**Scale/Scope**:

- 3 pages, 2 dialogs and about 4 feature components.
- 1 new endpoint and 4 changed ones, 1 migration, and 2 shared components moved.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Layering** | ✅ | The deposit, the add-on rules and `materials_used` live in `stringing/services.py`. The deposit reuses `sales.services.record_payment`. Counts are computed in `selectors.py`. Views stay thin. |
| I. Transactions and locks | ✅ | Create and deposit run in one `transaction.atomic`. Cancel and update keep their existing row lock. |
| I. Explicit state | ✅ | No new states. The client's move map mirrors `ALLOWED_TRANSITIONS`, and a test keeps them aligned. |
| **II. Testing** | ✅ | See the [contract tests](contracts/stringing-api.md#required-tests). Frontend: unit tests for `orderForm.ts` and `stringingDisplay.ts`; integration tests for the list, Details, Create/Edit and Cancel; axe checks. The existing sales tests guard the shared-component move. |
| **III. UX consistency** | ✅ | Shared UI components, formatters and `STATUS_BADGES.stringing` only. Each view has loading, empty, error and success states. Cancel needs a reason, the materials choice and a confirmation tick. Every money change ends with a toast. Field errors appear inline. |
| **IV. Performance** | ✅ | One aggregate query for counts. List and detail keep `order_queryset()` with `select_related`. Query counts are asserted. |
| **Append-only / money / constraints / migrations** | ✅ | Events are append-only. Money is `DecimalField` and strings. Five new DB constraints. One additive migration with safe defaults; no applied migration is rewritten. |
| **Security** | ✅ | A deposit needs `sales.record_payment`. Cancel and refund keep their permissions. Idempotency keys are scoped to the user who created them. Customer usability is checked. |
| **New dependencies** | ✅ | None. |

**Gate result**: PASS before research, and PASS again after design.

**Follow-ups** (outside this scope):

- The server could expose `allowed_transitions` on the order instead of the client mirror (R6).
- A backend defaults endpoint, if prices must change without a frontend rebuild (R2).
- Order history isn't shown in Details yet; the endpoint exists.

## Project Structure

### Documentation (this feature)

```text
specs/007-stringing-ui/
├── plan.md  research.md  data-model.md  quickstart.md
├── contracts/stringing-api.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
backend/stringing/
├── models.py              # add-on/colour/store fields, materials_used, client_transaction_id, constraints, total_amount
├── migrations/0007         # fields + constraints
├── services.py            # create (+deposit, idempotency), update (new editable fields, total), cancel (materials_used)
├── selectors.py           # ORDER_TOTAL with add-ons, filter split, status_counts, revenue gross_add_ons
├── serializers.py         # new fields, add_ons_total, DepositSerializer, cancel materials_used, counts
├── views.py / urls.py     # status-counts view; create 200/201 + IntegrityError retry
└── tests/                 # test_addons.py, test_create_deposit.py, test_status_counts.py, + updated tests

frontend/src/
├── config.ts                         # stringing default prices (VITE_STRINGING_*)
├── api/stringing.ts                  # new fields, create/cancel bodies, statusCounts
├── components/CustomerPicker.tsx     # moved from features/sales
├── components/LeaveGuard.tsx         # moved; title prop
├── lib/payments.ts                   # PAYMENT_METHODS, paymentMethodLabel (moved)
├── features/stringing/
│   ├── StringingOrdersPage.tsx       # list, chips, search, filters, Details host (?order=)
│   ├── OrderDetailsDialog.tsx        # stepper, details, breakdown, payments, status change
│   ├── StringingOrderFormPage.tsx    # create + edit; InvoicePanel.tsx
│   ├── CancelStringingOrderPage.tsx
│   ├── StringingPaymentDialog.tsx    # receipt or refund
│   ├── orderForm.ts  stringingDisplay.ts  hooks.ts
│   └── *.test.ts(x)
├── routes/workAreas.ts               # /stringing → real page; children new, :id/edit, :id/cancel
└── styles/components/_stringing.scss # stepper, invoice panel (tokens only)
```

**Structure Decision**: the same web-app layout as 005 and 006. Backend changes stay in
`stringing`; it only calls `sales.services.record_payment` and
`customers.services.ensure_usable`, as before.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| A separate status-counts endpoint | The chips need counts for every status under the current filters (FR-002) | Six list calls per view multiply round trips and queries. Adding counts to the paginated list would change a shared contract. |
| The client mirrors the transition map | Offer only valid moves (FR-013) without a serializer change | A server-provided map is cleaner but not needed now. A unit test pins the mirror, and the server still enforces it. |
