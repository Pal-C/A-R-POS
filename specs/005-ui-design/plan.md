# Implementation Plan: Design System, App Shell and Products Screens

**Branch**: `005-ui-design` | **Date**: 2026-11-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-ui-design/spec.md`

## Summary

This feature has four parts:

- **Design system**: the Figma references become design tokens and a themed Bootstrap build,
  plus a set of shared React components (buttons, fields, table, pagination, KPI card, badge,
  modal, banner, toast and the confirmation step).
- **App shell**: the feature-004 shell gets a navy sidebar and a page header with a sync pill and
  user badge.
- **Products screens**: the Inventory area gets the product list with KPI cards, Add, Edit,
  Remove, Reactivate and Receive Stock.
- **Products backend**: Model and Supplier fields, an append-only product history with a
  reason, atomic starting stock and stock edits, a conflict check on each changed field, and
  enforced cost visibility.

**Technical approach**:

- **Theming**: Bootstrap is compiled from Sass with our tokens
  ([R1](research.md#r1-theming-bootstrap-to-match-the-references-fr-001-fr-002)).
- **Fonts and icons**: self-hosted fonts ([R2](research.md#r2-typography)) and lucide icons
  ([R3](research.md#r3-icons)).
- **Page headers**: each route's `handle` supplies its title and subtitle
  ([R4](research.md#r4-page-header-metadata-and-routing)).
- **Sync pill**: driven by the API client ([R5](research.md#r5-sync-status-pill-fr-007)).
- **Product changes**: new `catalog/services.py` functions with a `ProductEvent` audit table,
  reusing the inventory services
  ([R6](research.md#r6-product-audit-history-fr-010-fr-016),
  [R7](research.md#r7-product-services-and-concurrency-fr-011-to-fr-013)).

## Technical Context

**Language/Version**: TypeScript ~6.0 (strict), React 19.3, Vite 8.3. Backend: Python 3.15,
Django 6.1, DRF 3.18.

**Primary Dependencies**:

- Existing: react-router, @tanstack/react-query, axios, bootstrap.
- **New runtime**: `lucide-react` ^1.82, `@fontsource/signika` ^5.3, `@fontsource/noto-sans`
  ^5.3.
- **New dev**: `sass-embedded` ^1.108, `axe-core` ^4.14.
- Backend: no new dependencies.

**Storage**: PostgreSQL. One migration: `catalog.Product.model` and `.supplier`, plus the new
`catalog.ProductEvent` table with a check constraint and an index.

**Testing**:

- Backend: Django `TestCase`, `APITestCase` and `TransactionTestCase`, with query-count
  assertions.
- Frontend: Vitest + Testing Library + MSW, with the axe-core helper.

**Target Platform**: Chrome or Edge on store desktops (1280 px and up) and tablets (768 px and
up).

**Project Type**: web application (frontend-heavy, with a focused backend addition in
`catalog`).

**Performance Goals**:

- Main JS ≤ 300 KB gzipped (about 155 KB expected, [R12](research.md#r12-bundle-budget-principle-iv)).
- Search results and list updates ≤ 100 ms after the debounce.
- Product list at 2 queries, detail at 2, history at 2, summary at 1
  ([contract](contracts/products-api.md#query-budgets)).
- **Checkout-path impact**: none. Sales code is untouched. `update_product` takes the same
  product row lock as sales, but only for the length of one edit transaction.

**Constraints**:

- Bootstrap-based shared components only (Principle III).
- No hardcoded colors outside `_tokens.scss`.
- Money is kept as strings.
- History is append-only.
- Cost data is never sent to users without the permission.

**Scale/Scope**:

- About 18 shared components and 4 layout components.
- 3 product pages and 3 dialogs.
- 1 new model, 4 services and 3 changed or new endpoints.
- About 1,000 products.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How this plan complies |
|---|---|---|
| **I. Layering** | ✅ | Product create, update, deactivate and reactivate move from the ViewSet into `catalog/services.py`. Stock changes go through `inventory.services` only. Views and serializers stay thin. On the frontend, HTTP lives only in `src/api/`, and pages use hooks in `features/products/hooks.ts`. |
| I. Transactions and locks | ✅ | Every service runs in `transaction.atomic`. `update_product` locks the product with `select_for_update` before comparing and writing, and the inventory services reuse that lock in the same transaction. |
| I. Explicit state | ✅ | `ProductEvent.Action` uses TextChoices. Dedicated deactivate and reactivate services check the current state. The badge mapping uses typed unions. |
| I. Static checks | ✅ | ruff; `tsc -b` strict; eslint. Each component is in its own file, under 500 lines. |
| **II. Testing** | ✅ | See the [contract test list](contracts/products-api.md#required-tests-backendcatalogtests): services (success and every rejection), the model constraint, the API (401/403/400/409/success, hidden cost), query counts, and concurrency (same-field conflict, stock edit vs sale). Frontend: unit tests for each component, formatter and the badge mapping; integration tests for the shell (nav, sync pill, user badge, collapse) and every Products flow; axe checks. |
| **III. UX consistency** | ✅ | This feature creates the shared components the principle requires, built on Bootstrap. Formatters are shared. Every view has loading, empty, error and success states. Remove and Reactivate need a reason plus a confirmation. Everything is keyboard-operable and meets WCAG AA (R1 contrast table, axe). Terminology: "Services" appears only as a nav label, and the area keeps "Stringing Orders". |
| **IV. Performance** | ✅ | Query counts are asserted. Summary is one aggregate query. Products pages are lazy-loaded. The bundle is checked. No impact on the checkout path. |
| **Append-only history** | ✅ | `ProductEvent` has no update or delete path and a read-only admin. Every event records the user and time. Stock changes stay in `InventoryMovement`. `PROTECT` foreign keys. |
| **Money / DB constraints / migrations** | ✅ | Decimals are stored as strings in the event JSON, and the existing price checks stay. New constraint: an event reason is required for every action except CREATED. One forward migration. |
| **Security** | ✅ | `catalog.view_product_cost` is now enforced on reads, writes, history and the summary. `catalog.adjust_stock` is enforced for stock edits. Deactivate and reactivate need a reason. |
| **New dependencies justified** | ✅ | sass-embedded (R1), fonts (R2), lucide-react (R3), axe-core (R10). Alternatives are in research. |

**Gate result**: PASS before research, and PASS again after design.

**Follow-ups recorded** (pre-existing, outside this scope; T044):

- `SaleItemSerializer` exposes cost. It will be handled in 006.
- `/api/inventory/adjustments/` doesn't check `catalog.adjust_stock`. It will be handled in an
  inventory follow-up.
- Product history is exposed by the API but not yet shown on screen. A "History" tab on Edit
  Product is a candidate for a later feature.
- The history endpoint uses 3 queries, not the 2 in the contract: an extra existence check
  returns 404 for unknown products. The contract has been updated to match.

## Project Structure

### Documentation (this feature)

```text
specs/005-ui-design/
├── plan.md
├── research.md            # R1–R12
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── products-api.md
│   └── ui-components.md
├── checklists/requirements.md
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── catalog/
│   ├── models.py                 # Product.model/.supplier; ProductEvent (+constraint, index)
│   ├── migrations/0003_product_model_supplier_productevent.py
│   ├── services.py               # create/update/deactivate/reactivate_product, ProductConflict
│   ├── serializers.py            # cost gating; ProductCreate/Update(changes, expected, reason); ProductEvent
│   ├── views.py                  # ViewSet delegates to services; deactivate/reactivate reason; history action
│   ├── admin.py                  # ProductEvent read-only
│   └── tests/                    # test_product_services.py, test_product_events.py, test_products_api.py (+), test_product_concurrency.py
└── inventory/views.py            # summary: + inventory_value (permission-gated)

frontend/
├── package.json                  # + lucide-react, @fontsource/*, sass-embedded, axe-core
└── src/
    ├── main.tsx                  # import styles/main.scss + fonts; ToastProvider
    ├── styles/
    │   ├── _tokens.scss          # design tokens -> Bootstrap vars + --ar-* custom props
    │   ├── main.scss             # Bootstrap partials + base + component styles
    │   └── components/*.scss     # one partial per shared component
    ├── lib/
    │   ├── format.ts             # money/date/count formatters, parseMoneyInput, initials
    │   ├── statusBadges.ts       # status → label/tone
    │   └── connection.ts         # online/offline store
    ├── api/
    │   ├── client.ts             # + connection status updates
    │   ├── catalog.ts            # model/supplier, optional cost, last_event, update(changes,expected,reason), deactivate/reactivate/history
    │   └── inventory.ts          # summary.inventory_value?
    ├── components/
    │   ├── QueryState.tsx        # restyled
    │   └── ui/                   # Button, IconButton, fields, SearchBox, FilterMenu, StatusChips, DataTable,
    │                             # Pagination, KpiCard, StatusBadge, Modal, Banner, ConfirmCheck, Toast, Card
    ├── layouts/
    │   ├── AppLayout.tsx         # sidebar + header + skip link + <main>
    │   ├── Sidebar.tsx  PageHeader.tsx  SyncPill.tsx  UserBadge.tsx
    ├── routes/
    │   ├── workAreas.ts          # navLabel/title/subtitle/icon/children; inventory area; /products redirect
    │   └── router.tsx            # handle metadata, child routes
    ├── features/products/
    │   ├── ProductsPage.tsx      # KPIs, search, filters, table, pagination, dialogs
    │   ├── ProductFormPage.tsx   # add + edit (route param)
    │   ├── ProductForm.tsx       # fields, validation, diffing for changes/expected
    │   ├── RemoveProductDialog.tsx  ReactivateProductDialog.tsx  ReceiveStockDialog.tsx
    │   ├── hooks.ts              # useProducts, useProduct, useInventorySummary, mutations + invalidation
    │   └── *.test.tsx
    └── test/
        └── axe.ts                # expectNoAxeViolations
```

**Structure Decision**: web application.

- Shared UI goes in `components/ui` and `layouts`.
- Screens are grouped by feature under `features/<area>`, a new convention that 006 and 007
  follow.
- Backend changes stay inside `catalog`, plus one view in `inventory`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `ProductEvent` repeats the event-table pattern of stringing and pre-orders | Each app owns its audit trail (same decision as 002 and 003) | A generic audit table would need generic foreign keys and a data migration of two existing tables |
| The PATCH body changes shape (`changes`, `expected`, `reason`) instead of being flat | Per-field conflict detection needs the editor's original values, and a reason is mandatory | A flat PATCH with an `updated_at` version would report false conflicts on every sale that touches the product |
