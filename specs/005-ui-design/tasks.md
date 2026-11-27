---
description: "Task list for Design System, App Shell and Products Screens"
---

# Tasks: Design System, App Shell and Products Screens

**Input**: Design documents from `/specs/005-ui-design/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/products-api.md,
contracts/ui-components.md, quickstart.md

**Tests**: Required (constitution Principle II, spec SC-004 and SC-005). Within each story, write
the tests first and confirm they fail.

**Organization**: Tasks are grouped by user story: US1 shell and design system, US2 product list
and KPIs, US3 add and edit with audit, US4 receive, remove and reactivate.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Add the runtime dependencies `lucide-react@^1.82`, `@fontsource/signika@^5.3` and `@fontsource/noto-sans@^5.3`, and the dev dependencies `sass-embedded@^1.108` and `axe-core@^4.14`, to frontend/package.json (run `npm install` in `frontend/`).
- [X] T002 [P] Create frontend/src/styles/_tokens.scss with the token table from research R1: colors, the Signika and Noto Sans type scale, spacing, radii and shadows. Map them onto the Bootstrap Sass variables (`$primary`, `$body-bg`, `$font-family-sans-serif`, `$headings-font-family`, `$border-radius*`, `$table-*`, `$btn-*`, `$input-*`, `$focus-ring-*`) and emit them as `--ar-*` custom properties.
- [X] T003 Create frontend/src/styles/main.scss, which imports the tokens, the Bootstrap partials listed in research R1, and `components/*` partials. In frontend/src/main.tsx, replace the `bootstrap.min.css` import with `styles/main.scss`, and import the latin subsets of `@fontsource/signika` 600/700 and `@fontsource/noto-sans` 400/500/600.
- [X] T004 [P] Create frontend/src/test/axe.ts with `expectNoAxeViolations(container)`. It runs `axe.run` with color-contrast disabled (jsdom can't compute it) and fails on `serious` or `critical` impact (research R10).

---

## Phase 2: Foundational (blocks all stories)

### Tests first

- [X] T005 [P] Write unit tests in frontend/src/lib/format.test.ts:
  - `formatMoney` with 0 and 2 decimals, thousands separators and negative values;
  - `formatDate` and `formatDateTime` in Asia/Manila across a UTC day boundary;
  - `parseMoneyInput`: accepts `₱1,200.5` as `1200.50` and rejects `abc`, `1.234` and `-1`;
  - `initials`: "Maria Reyes" gives MR, "solo" gives S.
- [X] T006 [P] Write unit tests in frontend/src/lib/statusBadges.test.ts: every value of every domain in data-model.md StatusBadgeSpec maps to the listed label and tone, and an unknown value falls back to a muted badge that shows the raw value.
- [X] T007 [P] Write unit tests in frontend/src/lib/connection.test.ts, and extend frontend/src/api/client.test.ts:
  - an HTTP response (200, 404 or 500) sets the status to `online`;
  - a network error sets it to `offline`;
  - the `window` `offline` and `online` events update it;
  - subscribers are notified.
- [X] T008 [P] Write backend model tests in backend/catalog/tests/test_product_events.py:
  - the `productevent_reason_required` constraint rejects a blank reason for UPDATED, DEACTIVATED and REACTIVATED, and allows it for CREATED (data-model.md ProductEvent.reason, ProductEvent.action);
  - deleting a product that has events is blocked by PROTECT.

### Implementation

- [X] T009 Add `Product.model` (CharField 100, blank) and `Product.supplier` (CharField 150, blank) to backend/catalog/models.py (data-model.md Product.model, Product.supplier). Add the `ProductEvent` model (data-model.md ProductEvent.product, ProductEvent.action, ProductEvent.changes, ProductEvent.reason, ProductEvent.performed_by, ProductEvent.created_at) with the check constraint and index. Generate backend/catalog/migrations/0003_product_model_supplier_productevent.py. Register `ProductEvent` as read-only in backend/catalog/admin.py. T008 must pass.
- [X] T010 [P] Implement frontend/src/lib/format.ts (contracts/ui-components.md Formatters) and add `VITE_STORE_TIME_ZONE` (default `Asia/Manila`) to frontend/src/vite-env.d.ts and frontend/.env.example. T005 must pass.
- [X] T011 [P] Implement frontend/src/lib/statusBadges.ts (data-model.md StatusBadgeSpec). T006 must pass.
- [X] T012 Implement frontend/src/lib/connection.ts (a `useSyncExternalStore` store plus `useConnectionStatus`) and wire it into the response interceptor in frontend/src/api/client.ts. T007 must pass.
- [X] T013 [P] Update frontend/src/api/catalog.ts to match contracts/products-api.md:
  - `Product` gains `model` and `supplier`; `cost_price` becomes optional; add `ProductDetail` with `last_event`;
  - `ProductCreate` gains `initial_stock`;
  - `update(id, {changes, expected, reason})`;
  - add `deactivate(id, reason)`, `reactivate(id, reason)` and `history(id, params)`;
  - remove `remove()`.

  Update frontend/src/api/inventory.ts with the optional `InventorySummary.inventory_value`, and update the matching cases in frontend/src/api/domain.test.ts.

**Checkpoint**: frontend and backend tests pass, and the migration applies cleanly.

---

## Phase 3: User Story 1 - App shell and visual language (P1) 🎯 MVP

**Goal**: every screen uses the new sidebar, header and shared components.

**Independent Test**: quickstart scenarios 1–5.

### Tests for US1

- [X] T014 [P] [US1] Write component tests in frontend/src/components/ui/*.test.tsx, one file per component, covering each component's contract in contracts/ui-components.md:
  - Button: variants, `busy` disables the button and sets `aria-busy`, icon;
  - fields: label association, error rendering with `aria-describedby`, the MoneyField ₱ prefix and string value, readOnly;
  - SearchBox: debounce and the clear button;
  - FilterMenu: opens, applies values, clears, shows the active count;
  - StatusChips: `aria-pressed` and onChange;
  - DataTable: loading, error and empty states, column render, row actions;
  - Pagination: the "Showing X–Y of N" text, `aria-current`, first and last page;
  - KpiCard: highlight and pending states;
  - StatusBadge: label and tone class;
  - Modal: Escape closes it, it doesn't close while busy, focus returns to the opener;
  - Banner and ConfirmCheck;
  - Toast: shown, auto-dismissed after 5 s, stays while hovered.

  Each file calls `expectNoAxeViolations`.
- [X] T015 [P] [US1] Write integration tests in frontend/src/layouts/AppLayout.test.tsx, replacing the old file:
  - the sidebar shows exactly Home, Sales, Inventory, Services, Customers and Pre-Orders in order, with no POS or Analytics;
  - the active item has `aria-current`;
  - "Services" leads to an `<h1>` "Stringing Orders";
  - each area's header shows its title and subtitle;
  - the user badge shows initials, display name and the Staff or Admin role, and Sign out works;
  - the pill shows "Synced", then "Offline" after a network error, then "Synced" again after a success;
  - "Skip to content" is the first focusable element and moves focus to `<main>`;
  - the collapsed sidebar at narrow width (via a `matchMedia` mock) keeps accessible names;
  - an axe check.

  Update frontend/src/routes/router.test.tsx for the new area list and the `/products` → `/inventory` redirect.

### Implementation for US1

- [X] T016 [P] [US1] Implement frontend/src/components/ui/Button.tsx and IconButton.tsx, plus frontend/src/styles/components/_buttons.scss.
- [X] T017 [P] [US1] Implement frontend/src/components/ui/fields.tsx (TextField, NumberField, MoneyField, SelectField, TextAreaField, CheckboxField) and ConfirmCheck.tsx, plus frontend/src/styles/components/_forms.scss.
- [X] T018 [P] [US1] Implement frontend/src/components/ui/SearchBox.tsx, FilterMenu.tsx and StatusChips.tsx, plus frontend/src/styles/components/_filters.scss.
- [X] T019 [P] [US1] Implement frontend/src/components/ui/DataTable.tsx and Pagination.tsx, plus frontend/src/styles/components/_table.scss. DataTable uses the restyled frontend/src/components/QueryState.tsx.
- [X] T020 [P] [US1] Implement frontend/src/components/ui/KpiCard.tsx, StatusBadge.tsx, Card.tsx and Banner.tsx, plus frontend/src/styles/components/_cards.scss and _badges.scss.
- [X] T021 [P] [US1] Implement frontend/src/components/ui/Modal.tsx (native `<dialog>`) and Toast.tsx (with `ToastProvider` and `useToast`), plus frontend/src/styles/components/_overlays.scss. Wrap the app in `ToastProvider` in frontend/src/main.tsx and frontend/src/test/renderApp.tsx. T014 must pass.
- [X] T022 [US1] Extend frontend/src/routes/workAreas.ts per data-model.md WorkArea:
  - add `navLabel`, `title`, `subtitle`, `icon` and `children`;
  - the areas are Home, Sales, Inventory (`/inventory`), Services (`/stringing`, title "Stringing Orders"), Customers and Pre-Orders (research R4);
  - remove the `/products` area.

  Update frontend/src/routes/router.tsx:
  - set `handle: {title, subtitle}` on each route;
  - generate the child routes;
  - redirect `/products` to `/inventory`.
- [X] T023 [US1] Implement frontend/src/layouts/Sidebar.tsx, PageHeader.tsx, SyncPill.tsx and UserBadge.tsx, plus frontend/src/styles/components/_shell.scss (the collapse below 992 px, and the active item in sky with a yellow bar). Rewrite frontend/src/layouts/AppLayout.tsx:
  - a skip link;
  - the sidebar;
  - the header from `useMatches()` handles;
  - `<main id="main" tabIndex={-1}>`.

  Remove the old top navbar. T015 must pass, and all feature-004 tests must still pass (update their selectors only where the markup changed).

**Checkpoint**: the shell matches the references; quickstart scenarios 1–5 pass.

---

## Phase 4: User Story 2 - Product list and KPIs (P1)

**Goal**: the Inventory screen with the KPI cards, search, filters, table and pagination, with cost gated by permission.

**Independent Test**: quickstart scenarios 6–8.

### Tests for US2

- [X] T024 [P] [US2] Write backend tests in backend/catalog/tests/test_products_api.py (extend it) and backend/inventory/tests/test_inventory_api.py (extend it):
  - `cost_price` is absent from list, detail and history responses without `catalog.view_product_cost`, and present with it;
  - the summary has `inventory_value` (Σ cost × stock over active products) only with the permission (data-model.md "Inventory summary", inventory_value);
  - the summary uses 1 query and the list 2 (`assertNumQueries`).
- [X] T025 [P] [US2] Write integration tests in frontend/src/features/products/ProductsPage.test.tsx (msw):
  - the KPI values render from the summary;
  - without the cost permission there is no Inventory Value card and no cost column;
  - search is debounced and sends `search=`;
  - the filter menu sends `category`, `stock_status` and `is_active`, and "Clear filters" resets them;
  - pagination sends `page=2` and the text reads "Showing 21–25 of 25 products";
  - status badges per row;
  - empty states for "No products yet" and "No products match";
  - error state;
  - an axe check.

### Implementation for US2

- [X] T026 [US2] Gate cost in backend/catalog/serializers.py: `ProductSerializer.to_representation` drops `cost_price` without `catalog.view_product_cost`, and the request is passed through context (research R8). In backend/inventory/views.py, add the permission-gated `inventory_value` to `InventorySummaryView` as one aggregate query. T024 must pass.
- [X] T027 [P] [US2] Implement frontend/src/features/products/hooks.ts: `useProducts(params)` (with `placeholderData: keepPreviousData`), `useInventorySummary()`, and the shared invalidation helper `invalidateProducts(queryClient)` for products, the summary and inventory.
- [X] T028 [US2] Implement frontend/src/features/products/ProductsPage.tsx:
  - four KpiCards (the Low Stock card highlighted; Inventory Value only with the permission);
  - a toolbar with SearchBox, FilterMenu (category, stock status, active), RECEIVE STOCK and ADD PRODUCT;
  - a DataTable with the Product, Type (subcategory, else category label), Brand, Price, Stock and Status columns and Edit/Remove or Reactivate row actions;
  - Pagination.

  The search, filter and page state live in URL search params so the view is bookmarkable. Register it as the Inventory area's page in frontend/src/routes/workAreas.ts. T025 must pass.

**Checkpoint**: Inventory list works end to end for the manager and cashier accounts.

---

## Phase 5: User Story 3 - Add and edit with audit (P1)

**Goal**: Add Product and Edit Product, with an atomic starting stock and stock edits, a required reason, history, and per-field conflict detection.

**Independent Test**: quickstart scenarios 9–11.

### Tests for US3

- [X] T029 [P] [US3] Write service tests in backend/catalog/tests/test_product_services.py:
  - `create_product` without starting stock writes a CREATED event and no movement;
  - with `initial_stock=89` it writes the event and a RESTOCK movement "Initial stock" in one transaction (data-model.md "Validation rules"; initial_stock ≥ 0);
  - `update_product` writes a single UPDATED event listing only the changed fields, with old and new values as strings;
  - a stock change writes an ADJUSTMENT_OUT or ADJUSTMENT_IN movement with the reason and records `movement_id`;
  - a blank reason, empty changes, and a key missing from `expected` are rejected;
  - a mismatched expected value on a changed field raises `ProductConflict` with the current values;
  - no conflict when an unchanged field (stock) changed concurrently;
  - a stock change without `catalog.adjust_stock`, or a cost change without `catalog.view_product_cost`, raises PermissionDenied;
  - model and supplier are trimmed.
- [X] T030 [P] [US3] Write API tests in backend/catalog/tests/test_products_api.py:
  - POST with `initial_stock`, and 403 when cost is sent without the permission;
  - PATCH with `{changes, expected, reason}` returns 200;
  - PATCH returns 400 for no reason, 403 for stock without the permission and 409 with `current`;
  - PUT returns 405;
  - the detail has `last_event` (2 queries);
  - `GET history/` is paginated, newest first, hides cost changes without the permission, and uses 2 queries;
  - 401 for every endpoint when anonymous.

  Update the existing `test_update_product` and `test_stock_quantity_cannot_be_updated_through_product_api` for the new PATCH shape.
- [X] T031 [P] [US3] Write concurrency tests in backend/catalog/tests/test_product_concurrency.py (`TransactionTestCase`, threads):
  - two editors change `selling_price` from the same expected value, one succeeds and the other gets `ProductConflict`;
  - a stock edit and a concurrent `deduct_stock_for_sale` serialize, with a correct final stock and two movements.
- [X] T032 [P] [US3] Write integration tests in frontend/src/features/products/ProductFormPage.test.tsx (msw):
  - Add: required-field validation stops the request; the server's field errors (a duplicate SKU) show next to the field; a successful save sends `initial_stock`, shows a toast and returns to `/inventory`; the cost field is hidden without the permission;
  - Edit: the form is prefilled and shows "Last updated <date> by <name>" and the Active badge; Save is disabled until something changes; the reason is required; only the changed fields are sent with their `expected` values; Stock is read-only without `catalog.adjust_stock`; a 409 shows the "changed by someone else" alert with the current values and keeps the user's input;
  - an axe check.

### Implementation for US3

- [X] T033 [US3] Implement backend/catalog/services.py: `create_product`, `update_product`, `ProductConflict`, and the helpers to diff and serialize values (research R7, data-model.md "Validation rules"). Every function runs in `transaction.atomic`, has a docstring stating its side effects, and calls `inventory.services.restock_product` and `adjust_stock` within the same transaction. T029 must pass.
- [X] T034 [US3] Update backend/catalog/serializers.py:
  - `ProductWriteSerializer`: the writable fields plus `model`, `supplier` and `initial_stock`, with the existing SKU and name validators;
  - `ProductUpdateSerializer`: `changes`, `expected` and `reason`, where `changes` is validated through the write serializer as a partial;
  - `ProductEventSerializer`, with `performed_by` `{id, username, display_name}` and cost changes stripped without the permission;
  - `last_event` on the detail view.

  Update backend/catalog/views.py:
  - `create` and `partial_update` delegate to the services, mapping `ProductConflict` to 409;
  - `update` (PUT) returns 405;
  - add the `history` action (paginated, `select_related`);
  - the detail queryset prefetches the latest event.

  T030 and T031 must pass, and ruff must be clean.
- [X] T035 [P] [US3] Implement frontend/src/features/products/ProductForm.tsx (data-model.md ProductFormValues):
  - fields in the reference layout: a 3-column grid that collapses to 1 column below 768 px;
  - client validation mirroring the server rules;
  - `diffValues(initial, current)` produces the `changes` and `expected` objects;
  - the info banner;
  - CANCEL and SAVE buttons.
- [X] T036 [US3] Implement frontend/src/features/products/ProductFormPage.tsx (add vs edit from the route param, `useProduct(id)`, create and update mutations with `invalidateProducts`, a toast on success, the 409 alert showing current values, server errors mapped to fields). Add the `new` and `:id/edit` child routes with their handles ("Add Product" / "Create a product record with price, cost and stock"; "Edit Product" / "Update product details, price and stock threshold") in frontend/src/routes/workAreas.ts. T032 must pass.

**Checkpoint**: Add and Edit work end to end; history and movements are verified in quickstart scenarios 9–11.

---

## Phase 6: User Story 4 - Receive, remove and reactivate (P2)

**Goal**: Receive Stock, plus Remove and Reactivate dialogs with a reason and confirmation.

**Independent Test**: quickstart scenarios 12–13.

### Tests for US4

- [X] T037 [P] [US4] Write backend tests in backend/catalog/tests/test_product_services.py and test_products_api.py:
  - `deactivate_product` and `reactivate_product` require a reason, write a DEACTIVATED or REACTIVATED event, and reject the already-in-state case;
  - the API returns 400 for a blank reason;
  - the existing `test_deactivate_product` and `test_reactivate_product` are updated to send a reason;
  - past sales are unaffected by deactivation.
- [X] T038 [P] [US4] Write integration tests in frontend/src/features/products/ProductDialogs.test.tsx (msw):
  - Receive Stock: the quantity must be at least 1, the reference number is optional, the request goes to `/inventory/restocks/`, and a toast shows the new stock level with the list refreshed;
  - Remove: the summary with its badge and the remaining stock; the button is disabled until a reason is entered and the box ticked; success refreshes the list;
  - Reactivate: a reason is required, and success refreshes the list;
  - Escape closes the dialog and focus returns to the row action;
  - busy state;
  - an axe check.

### Implementation for US4

- [X] T039 [US4] Add `deactivate_product` and `reactivate_product` to backend/catalog/services.py. They lock the row, check the state, and write the event. Update the `deactivate` and `reactivate` actions in backend/catalog/views.py to require `reason` and delegate to the services. T037 must pass.
- [X] T040 [P] [US4] Implement frontend/src/features/products/ReceiveStockDialog.tsx. The product can be preselected from the row, or chosen in the dialog with a searchable select of active products. It uses `inventoryApi.restock`.
- [X] T041 [P] [US4] Implement frontend/src/features/products/RemoveProductDialog.tsx and ReactivateProductDialog.tsx, using Modal, TextAreaField, ConfirmCheck and Banner.
- [X] T042 [US4] Wire the dialogs into frontend/src/features/products/ProductsPage.tsx (the toolbar RECEIVE STOCK button and the row actions) with mutations, `invalidateProducts` and toasts. T038 must pass, and T025 must still pass.

**Checkpoint**: all four stories work; quickstart scenarios 1–13 pass.

---

## Phase 7: Polish & Cross-Cutting

- [X] T043 [P] Update frontend/README.md (styles and tokens, `components/ui` conventions, `features/<area>` layout, how to add a status badge or a page header) and backend/.env.example/frontend/.env.example (`VITE_STORE_TIME_ZONE`).
- [X] T044 [P] Record the follow-ups in specs/005-ui-design/plan.md "Follow-ups recorded":
  - the cost exposure in `SaleItemSerializer` (for 006);
  - the missing `catalog.adjust_stock` check on `/inventory/adjustments/`.
- [X] T045 Run all gates:
  - backend: `manage.py test`, `ruff check .`, `ruff format --check` on new and changed files, and `makemigrations --check`;
  - frontend: `lint`, `typecheck`, `test` and `build`.

  Fix every failure. Check that no hex color appears outside `_tokens.scss` (`grep -rnE "#[0-9a-fA-F]{3,6}" frontend/src --include=*.scss --include=*.tsx`).
- [X] T046 Check the bundle budget: the main JS stays at or under 300 KB gzipped (expected about 155 KB), the products pages are in a separate chunk, and the CSS size is recorded.
- [X] T047 Do a manual pass of specs/005-ui-design/quickstart.md scenarios 1–14, including a side-by-side comparison with the Figma PNGs (SC-003). Record the results and any design differences.
  - 2026-11-27: visually reviewed at 1440×1024 and 900 px against a throwaway `testserver` database: Product List, Edit Product, Remove dialog, shell and collapsed sidebar. Fixed during the review: white input background, form card width, narrow-logo fit, table horizontal scroll. Remaining intentional differences: outline (lucide) icons instead of filled; Type field added (maps the references' String or Overgrip categories); SKU required (the backend requires it, while the reference shows it as optional); POS and Analytics hidden (Q3).

---

## Phase 8: Review Fixes (from /code-review and /security-review, 2026-11-27)

- [X] T048 Anchor the `lib/` rule in the root .gitignore to `/lib/`, so `frontend/src/lib/` is committed.
- [X] T049 Ignore `?ordering=cost_price` for users without `catalog.view_product_cost` (`CostAwareOrderingFilter` in backend/catalog/views.py), with tests in test_cost_visibility.py.
- [X] T050 Show server errors that have no matching form field in an alert instead of dropping them (frontend/src/features/products/errorDisplay.ts, used by ProductFormPage and InventoryPage). Map `initial_stock` errors to Starting Stock.
- [X] T051 Map a SKU unique-constraint race to a 400 `{"sku": ...}` in `create_product` and `update_product` (using savepoints).
- [X] T052 Remove `is_active` from the editable fields. The Edit form shows Active read-only and points to Remove/Reactivate.
- [X] T053 Validate the deactivate/reactivate `reason` as text (`ReasonSerializer`). A non-text value returns 400, not 500.
- [X] T054 Make Receive Stock keep the chosen product across searches.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** comes first: T001, then T002–T004.
- **Foundational (Phase 2)** depends on Setup and blocks all stories. The backend tasks T008–T009 and the frontend tasks T005–T007 and T010–T013 can run in parallel.
- **US1 (Phase 3)** depends on Phase 2. US2–US4 use its components.
- **US2 (Phase 4)** depends on US1. Its backend part (T024 and T026) can start right after Phase 2.
- **US3 (Phase 5)** depends on US1. Its backend part (T029–T031 and T033–T034) can start right after Phase 2. The frontend part needs US2's hooks (T027).
- **US4 (Phase 6)** depends on US2 (the list page). Its backend part (T037 and T039) needs T033 (the services module).
- **Polish (Phase 7)** depends on all stories.

## Parallel Examples

```text
# Phase 2
T005 format.test | T006 statusBadges.test | T007 connection.test | T008 test_product_events.py

# US1 components (all different files)
T016 Button | T017 fields | T018 filters | T019 table | T020 cards/badges | T021 modal/toast

# Backend track alongside US1 frontend
T024 + T026 (cost gating, summary) -> T029–T031 + T033–T034 (services/API) -> T037 + T039
```

## Implementation Strategy

1. **MVP (Phases 1–3)**: the new shell and component library. Every existing page looks right.
2. **US2**: the Inventory list, the most-used view.
3. **US3**: Add and Edit with audit.
4. **US4**: Receive, Remove and Reactivate.
5. **Polish**: gates and design review. Then `/code-review` and `/security-review` before merge.
