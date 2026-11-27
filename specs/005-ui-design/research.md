# Research: Design System, App Shell and Products Screens

Package versions are the latest stable releases on 2026-11-27 (`npm view`).

## R1. Theming Bootstrap to match the references (FR-001, FR-002)

- **Decision**:
  - Compile Bootstrap from its Sass sources (`sass-embedded` ^1.108, dev only).
  - `src/styles/_tokens.scss` holds the design tokens (colors, type, spacing, radii, shadows).
    They are mapped onto Bootstrap's Sass variables (`$primary`, `$body-bg`, `$border-radius`,
    `$table-*`, `$btn-*`, and so on) and also emitted as CSS custom properties (`--ar-*`) for
    our components.
  - Only the Bootstrap partials we use are imported (grid, utilities, forms, buttons, tables,
    badge, modal, toasts, nav, dropdown, alert, spinner, pagination). This drops the unused CSS
    from the current 230 KB prebuilt file.
- **Rationale**:
  - The constitution mandates Bootstrap.
  - Sass variables are the supported way to retheme every component consistently.
  - CSS variables let our components read the same tokens at runtime.
- **Alternatives considered**:
  - Override the prebuilt CSS with `--bs-*` variables. Rejected: in Bootstrap 5.3 many
    components (buttons, tables) compute their colors at build time, so the overrides would be
    brittle and incomplete.
  - Tailwind. Rejected: it conflicts with the constitution.

**Tokens extracted from the references** (the Figma files themselves were not shared, so the
hex values are sampled from the PNGs and should be confirmed against Figma during design
review):

| Token | Value | Used for |
|---|---|---|
| `navy-900` | `#032D42` | sidebar, primary buttons, headings, Completed badge |
| `sky-300` | `#8EC8E4` | table headers, active nav item, product cards, In Progress badge |
| `yellow-400` | `#F5B800` | low-stock and ready badges, active-nav accent bar, highlighted KPI number |
| `ink-900` | `#111111` | text; black destructive-confirm button; Out of Stock and Cancelled badges |
| `grey-100` | `#F3F2F5` | page background, banners |
| `grey-300` | `#D9D9D9` | card and table borders |
| `grey-600` | `#6B6B6B` | secondary text |
| radius | 6 px controls, 8 px cards, pill badges | |

All the text and background pairs above meet WCAG AA (navy on white 14.6:1, ink on sky 11:1,
ink on yellow 12:1, white on navy 14.6:1). `sky-300` is never used for text on white.

## R2. Typography

- **Decision**:
  - Headings (page titles, card titles, "Products", "Cart"): **Signika** at 600/700 weight.
  - Body and UI: **Noto Sans** at 400/500/600.
  - Both are self-hosted through `@fontsource/signika` ^5.3 and `@fontsource/noto-sans` ^5.3,
    latin subset only.
- **Rationale**:
  - The references' semi-condensed headings and humanist UI text match these families.
  - Self-hosting avoids a runtime request to Google, which matters for privacy and for a
    counter machine with poor connectivity.
  - Each weight is a woff2 file of about 20 KB and isn't part of the JS bundle.
- **To confirm**: if the Figma file names different fonts, change only `_tokens.scss` and the
  two imports.

## R3. Icons

- **Decision**: `lucide-react` ^1.82, with individual named imports so unused icons are
  tree-shaken away.
- **Icon mapping**:

  | Area | Icon |
  |---|---|
  | Home | `House` |
  | Sales | `PhilippinePeso` |
  | Inventory | `Package` |
  | Services | `Ribbon` |
  | Customers | `Users` |
  | Pre-Orders | `Clock` |
  | (future) POS | `ShoppingCart` |
  | (future) Analytics | `ChartColumn` |

  Plus `Search`, `Funnel`, `Plus`, `SquarePen`, `X`, `TriangleAlert`, `ChevronDown` and
  `PackagePlus` for the controls.
- **Rationale**:
  - It has a peso icon.
  - It costs about 1 KB per icon used.
  - Icons are SVG, so they inherit `currentColor` and scale cleanly.
- **Alternatives considered**: Bootstrap Icons (no peso sign, and the font loads every glyph)
  and Font Awesome (heavier, with a separate SVG core).

## R4. Page header metadata and routing

- **Decision**: each route declares `handle: { title, subtitle }`. `AppLayout` reads the deepest
  match with `useMatches()` and renders the `PageHeader`.
- **`WorkArea` additions**:
  - `navLabel` ("Services") separate from `title` ("Stringing Orders");
  - `icon`;
  - optional child routes.
- **Inventory routes**:
  - `/inventory` is the product list.
  - `/inventory/new` is Add Product.
  - `/inventory/:id/edit` is Edit Product.
  - `/products` redirects to `/inventory`.

  The Remove, Reactivate and Receive Stock dialogs are modal state, not routes.
- **Rationale**: it is a single source of truth again, and screens don't render their own
  headers. Add and Edit are routes because the references show them as full pages (they also
  become bookmarkable). Removal is a modal in the references.

## R5. Sync status pill (FR-007)

- **Decision**: `src/lib/connection.ts` is a tiny external store read with
  `useSyncExternalStore`:
  - the API client's interceptors set it to `online` on any HTTP response (including 4xx/5xx,
    since the server was reached);
  - they set it to `offline` on `network` errors;
  - `window` `online`/`offline` events also update it.
- **Rationale**: no polling and no new dependency. It reflects the real request path, including
  the dev proxy.
- **Alternative considered**: periodic `/auth/me/` pings. Rejected as needless traffic.

## R6. Product audit history (FR-010, FR-016)

- **Decision**: a new append-only `catalog.ProductEvent` model:
  - `product` (FK, PROTECT);
  - `action` (TextChoices: CREATED, UPDATED, DEACTIVATED, REACTIVATED);
  - `changes` (JSON of `{field: [old, new]}`, with Decimals stored as strings);
  - `reason`;
  - `performed_by` (FK, PROTECT);
  - `created_at`.

  It is indexed on `(product, -created_at)` and read-only in the admin. A database check
  constraint requires a non-blank reason for every action except CREATED.
- **Rationale**: this mirrors `StringingOrderEvent` and `PreOrderEvent` (one audit table per
  app) and the constitution's append-only and constraint rules. Stock changes are already
  audited by `InventoryMovement`, so an UPDATED event lists `stock_quantity` together with the
  movement id.
- **"Last updated by"**: the detail view shows the latest event's user and time through
  `select_related` on a prefetched latest event. The list doesn't show it, so it adds no list
  queries.

## R7. Product services and concurrency (FR-011 to FR-013)

- **Decision**: a new `catalog/services.py`. Every function runs in `transaction.atomic` and
  has a docstring stating its side effects. Each one does the following:

  | Function | What it does |
  |---|---|
  | `create_product(*, user, data, initial_stock=0)` | Creates the product and a CREATED event. If the starting stock is above 0, it calls `inventory.services.restock_product(reason="Initial stock")`. |
  | `update_product(*, product_id, user, changes, expected, reason)` | Locks the row with `select_for_update`. For every changed field, compares the current value with `expected[field]`; any difference raises `ProductConflict`, which becomes 409. A stock change calls `adjust_stock(quantity_change=new-current, reason=reason)` and needs `catalog.adjust_stock`. Writes one UPDATED event listing only the fields that changed. |
  | `deactivate_product(*, product_id, user, reason)` | Sets the product inactive and writes a DEACTIVATED event. |
  | `reactivate_product(*, product_id, user, reason)` | Sets the product active and writes a REACTIVATED event. |

- **Rationale**:
  - **Concurrency**: checking only the changed fields avoids false conflicts. A sale that
    changes the stock (and `updated_at`) while a manager edits the price is not a conflict,
    while a real clash on the same field is caught.
  - **Layering**: the views stay thin, as Principle I requires.
- **Alternatives considered**: an `updated_at` version check, rejected because every sale
  touches `updated_at`, and a version integer column, which has the same problem.

## R8. Cost visibility (FR-014)

- **Decision**:
  - `ProductSerializer` drops `cost_price` from its output unless
    `request.user.has_perm("catalog.view_product_cost")`.
  - Writes that include `cost_price` without that permission return 403.
  - `InventorySummaryView` adds `inventory_value` (`Sum(F("cost_price") * F("stock_quantity"))`
    over active products) only for permitted users.
  - The frontend hides the cost field and the KPI card when `hasPermission` is false.
- **Rationale**: the constitution requires cost visibility to be gated. The permission already
  exists but wasn't enforced.
- **Known gaps outside this scope**:
  - `SaleItemSerializer` (`unit_cost_price`, `gross_profit`) also exposes cost.
  - `/inventory/adjustments/` doesn't check `catalog.adjust_stock`.

  Both are pre-existing and get follow-up tasks for features 006 and inventory.

## R9. Components and state

- **Decision**: our own thin React components under `src/components/ui/`, built on Bootstrap
  classes. There are no headless UI libraries.
  - **Modal**: a native `<dialog>` element. Its `showModal()` gives focus trapping, Escape
    handling and the top layer, and focus is restored to the opener on close.
  - **Toasts**: a small `ToastProvider` context, the only new piece of global state. It is
    global because confirmations must survive a navigation, for example after Save on
    `/inventory/new` returns to `/inventory`.
  - **Forms**: controlled components with a small `useForm` helper. Server field errors are
    mapped from `ApiError.fieldErrors`. No form library is needed for forms this size.
- **Rationale**: it keeps dependencies minimal (constitution) and keeps the components visibly
  "ours" for features 006 and 007.

## R10. Accessibility testing (SC-004)

- **Decision**: `axe-core` ^4.14 as a dev dependency, wrapped in a 10-line `expectNoAxeViolations(container)`
  test helper that fails on `serious` and `critical` impact. It runs in the shell test and on
  every Products screen and dialog. Color contrast can't be computed in jsdom, so R1's contrast
  table plus a manual check in quickstart covers it.
- **Alternative considered**: `vitest-axe` (0.1.0), rejected because it is unmaintained.

## R11. Formatters (FR-004)

- **Decision**: `src/lib/format.ts`:
  - `formatMoney(value, { decimals })` uses `Intl.NumberFormat('en-PH', { style: 'currency',
    currency: 'PHP' })` on the Decimal string, with no float arithmetic beyond display.
  - `formatDate` and `formatTime` use the `VITE_STORE_TIME_ZONE` env variable (default
    `Asia/Manila`, matching the backend's `STORE_TIME_ZONE`).
  - `formatCount` adds thousands separators.
- **Money input**: `parseMoneyInput` validates `^\d+(\.\d{1,2})?$` after stripping `₱` and
  commas, and keeps the value as a string.

## R12. Bundle budget (Principle IV)

| Piece | Gzipped size |
|---|---|
| Current main JS | 133.8 KB |
| lucide icons | about 1 KB each, about 20 icons |
| New components | about 15 KB |
| Products feature | about 10 KB, lazy-loaded |

The expected main JS is about 155 KB, well under 300 KB. The CSS should shrink from the 30.7 KB
prebuilt Bootstrap file to about 25 KB with partial imports.
