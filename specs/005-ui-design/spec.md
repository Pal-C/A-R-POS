# Feature Specification: Design System, App Shell and Products Screens

**Feature Branch**: `005-ui-design`

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "For the design, use these Figma designs as reference." There are 13
reference screens:

- View Sales
- Create Sale (with customer association)
- Edit Sale, with and without customer association
- Cancel Sale
- Product List
- Add Product
- Edit Product
- Remove Product
- Stringing Orders home
- Create Stringing Order
- Stringing Order details
- Cancel Stringing Order

## Clarifications

### Session 2026-11-27

- Q: How much goes into this feature? → A: 005 delivers the design system, the app shell and the
  Products (Inventory) screens. Sales screens follow in feature 006 and Stringing Order screens
  in feature 007. Both reuse this feature's components.
- Q: How should design items the back office doesn't support yet be handled? → A: A mix. Each
  feature adds the small back-office pieces its screens need. Larger business-rule changes are
  deferred to their own features: editing finalized sales, the stock-handling choice when
  cancelling a sale, and "materials used" when cancelling a stringing order. For this feature
  that means:
  - product Model and Supplier fields;
  - a reason stored for every product edit, stock change and removal, in an audit history;
  - the starting stock on create and stock edits on Edit, each recorded as an inventory movement.
- Q: What should the sidebar show? → A: The sidebar shows Home, Sales, Inventory, Services,
  Customers and Pre-Orders in the reference order. "Services" is the sidebar label only; the
  Services area and its records keep the "Stringing Orders" term. POS and Analytics are hidden
  until they exist.

## Overview

This feature gives the staff app its visual identity and its first fully working area,
following the Figma references:

- **Visual language**: a navy sidebar, a header with a sync pill and the signed-in user,
  light-blue table headers, KPI cards and status pills.
- **Shared components**: every later screen is built from them.
- **Products**: the Products screen and the Add, Edit and Remove flows, behind the sidebar's
  Inventory item.

Feature 004 delivered the shell, sign-in, routing and API access; this feature restyles it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent app shell and visual language (Priority: P1)

A signed-in staff member sees the Ace&Rally layout on every screen.

- **Sidebar**: a navy sidebar with the logo and icon navigation. The current area is
  highlighted in light blue with a yellow accent.
- **Header**: the page title and subtitle, a "Synced" or "Offline" pill, and the staff member's
  initials, name and role, with Sign out.

Every screen uses the same buttons, inputs, tables, badges, banners and dialogs.

**Why this priority**: All other screens, in this feature and in 006 and 007, are built from
these pieces. The constitution (Principle III) forbids one-off styling of patterns that have a
shared component.

**Independent Test**: Sign in and visit each area. The sidebar, header and component styles
match the references. The active item is highlighted, and the header shows the signed-in staff
member. Everything is keyboard-operable and passes WCAG 2.1 AA checks.

**Acceptance Scenarios**:

1. **Given** a signed-in staff member, **When** any area is opened, **Then** the sidebar shows
   Home, Sales, Inventory, Services, Customers and Pre-Orders with icons, and highlights the
   current area. The header shows that area's title and subtitle, and the staff member's
   initials, display name and role.
2. **Given** the server is reachable, **When** staff look at the header, **Then** the pill reads
   "Synced". **When** a request fails because the server can't be reached, **Then** the pill
   reads "Offline", and it returns to "Synced" after the next successful request.
3. **Given** any amount of money, **When** it is displayed, **Then** it uses the peso sign and
   thousands separators. Unit prices in tables may omit the decimals; totals, form values and
   KPI values use the format their component defines, the same way everywhere.
4. **Given** a window narrower than 992 px, **When** the app is used, **Then** the sidebar
   collapses to icons only, labels show as tooltips, and there is no horizontal page scroll.
5. **Given** keyboard-only use, **When** staff tab through any screen, **Then** focus is always
   visible and follows reading order. A "Skip to content" link is available.

---

### User Story 2 - See stock at a glance and find products (Priority: P1)

Staff open Inventory and see:

- **Four KPI cards**:
  - Total Products (active in catalog);
  - Low Stock (at or below threshold), highlighted;
  - Out of Stock (cannot be sold);
  - Inventory Value (at cost).
- **A product table**: product, type, brand, price, stock, and a status badge (In Stock, Low
  Stock or Out of Stock), with row actions.

They can search by name, type or brand, filter, and page through results.

**Why this priority**: This is the area staff check most when restocking. The back office
already supports all of its data.

**Independent Test**: With seeded products, the KPI values match the data. Searching "BG66"
finds it. Filtering by Low Stock shows only low-stock products. Page 2 shows the next
products, and the "Showing X–Y of N products" text is correct.

**Acceptance Scenarios**:

1. **Given** products exist, **When** Inventory opens, **Then** the cards show:
   - the number of active products;
   - the number of active products with stock above zero and at or below their threshold;
   - the number of active products with zero stock;
   - the total of cost × stock for active products.
2. **Given** a staff member without the "view product cost" permission, **When** Inventory
   opens, **Then** the Inventory Value card and every cost field are hidden, and the back office
   doesn't send cost data to them.
3. **Given** the table, **When** staff search or filter by category, stock status, or
   active/inactive, **Then** the list updates and the count and page numbers reflect the
   results.
4. **Given** no products match, **When** the list is empty, **Then** an empty state appears.
   With no filters it says "No products yet" and offers "Add product"; with filters it says
   "No products match" and offers "Clear filters".
5. **Given** an inactive product, **When** it is listed (with the inactive filter), **Then** it
   shows an "Inactive" badge and a Reactivate action instead of Remove.

---

### User Story 3 - Add and edit products with an audit trail (Priority: P1)

Staff add a product with:

- name, category, brand, model, size/variant and supplier;
- cost and selling price;
- starting stock, low-stock threshold and SKU;
- an active toggle.

They edit an existing product's details, price, threshold and stock. Every edit requires a
reason, and the change is recorded with their name and the time. Stock changes are recorded as
inventory movements.

**Why this priority**: This is needed to maintain the catalog that sales and pre-orders depend
on. The references require the audit reason.

**Independent Test**:

1. Add "BG66 Ultimax" with a starting stock of 89. It appears In Stock with 89 units, and the
   inventory history shows a stock increase of 89.
2. Edit its selling price with the reason "Supplier price increase". The product's history shows
   the old and new price, the reason, the staff member and the time.
3. Change its stock from 89 to 85 with a reason. A stock decrease of 4 is recorded.

**Acceptance Scenarios**:

1. **Given** the Add Product form, **When** staff fill in the required fields (name, category,
   SKU, selling price, cost) and save, **Then** the product is created. Any starting stock is
   recorded as an inventory increase in the same step. A confirmation names the product, and
   staff return to the list.
2. **Given** invalid input, **When** staff save, **Then** nothing is saved and each error is
   shown next to its field. Invalid input means:
   - a missing name or SKU;
   - a duplicate SKU;
   - a negative price, stock or threshold;
   - a non-numeric amount.
3. **Given** the Edit Product form, **When** staff change any field, **Then** "Reason for change"
   is required. Saving records the changed fields (old and new values), the reason, the staff
   member and the time. Stock changes are recorded as inventory adjustments with that reason.
   All of this happens in one step: either everything is saved or nothing is.
4. **Given** the Edit form, **When** nothing has changed, **Then** Save is disabled.
5. **Given** a staff member without the "adjust stock" permission, **When** they edit a product,
   **Then** Stock Quantity is read-only, and the back office refuses stock changes from them.
6. **Given** two staff edit the same product at the same time, **When** the second saves after
   the first, **Then** they are told the product changed and are shown the current values.
   Their edit is not silently overwritten.
7. **Given** the Edit form, **When** it opens, **Then** it shows "Last updated <date> by <name>"
   and an Active or Inactive badge.

---

### User Story 4 - Receive stock, and remove or restore products (Priority: P2)

Staff can:

- receive a delivery for a product (quantity plus an optional reference number);
- remove a discontinued product: it is deactivated, not erased, after a reason and an "Are you
  sure? This hides the product from POS" confirmation;
- restore an inactive product.

**Why this priority**: These are less frequent than browsing and editing, but needed to keep
stock and the catalog accurate.

**Independent Test**: Receive 10 units of a product and see its stock go up by 10. Remove an
out-of-stock product with a reason: it disappears from the active list and shows as Inactive
under the inactive filter. Reactivate it.

**Acceptance Scenarios**:

1. **Given** a product, **When** staff choose Receive Stock and enter a quantity of 1 or more,
   **Then** the stock increases, a restock movement is recorded, and a confirmation shows the
   new stock level.
2. **Given** the Remove dialog, **When** the reason is empty or the box is unticked, **Then** the
   Remove button is disabled.
3. **Given** a reason and the ticked box, **When** staff confirm, **Then** the product is
   deactivated, the reason is stored in its history, and past sales are unchanged.
4. **Given** an inactive product, **When** staff choose Reactivate, **Then** it is active again
   and the action is recorded in its history.

---

### Edge Cases

- **Long names**: long product names truncate with an ellipsis and show in full on hover or
  focus. Very large numbers don't break KPI cards.
- **Slow responses**: every view shows its loading state. Save, Remove and Receive buttons show a
  busy state and can't be pressed twice.
- **Removing a product with stock left**: allowed, and the dialog shows the remaining stock so
  staff know.
- **Dialogs**: they trap focus and close on Escape, except while saving. After closing, focus
  returns to the button that opened the dialog.
- **Offline mid-edit**: the form keeps what was typed and shows the "Cannot reach the server"
  alert. The pill shows "Offline".
- **Permissions**: staff without a permission don't see the related action, and the back office
  enforces it regardless.

## Requirements *(mandatory)*

### Functional Requirements

**Design system**

- **FR-001**: The app MUST use one shared set of design tokens taken from the references:
  - **Colors**: navy primary; light blue for accents, table headers and the active nav item;
    yellow for highlights; light grey page background; white cards with subtle borders;
    text greys.
  - **Type scale and font**.
  - **Spacing, corner radii and shadows**.
- **FR-002**: The app MUST provide shared components for each pattern in the references, and
  screens MUST use them (constitution Principle III):
  - sidebar navigation;
  - page header (title, subtitle, sync pill, user badge);
  - buttons: primary, outlined secondary, black destructive-confirm, and icon buttons;
  - form fields: text, select, money, number and checkbox, with labels and inline errors;
  - search box;
  - filter button and menu;
  - status filter chips with counts (used by feature 007);
  - data table: styled header, row actions, empty state, loading state, and pagination with
    the "Showing X–Y of N" text;
  - KPI card, including a highlighted variant;
  - status badge;
  - modal dialog;
  - info/warning banner;
  - confirmation checkbox;
  - toast confirmation.
- **FR-003**: Status badges MUST use one mapping from each status to its label and style across
  the app. The mapping covers stock status, active/inactive, and the sale, stringing order and
  pre-order statuses, so that 006 and 007 reuse it. Labels use the constitution's terminology.
- **FR-004**: Money, numbers, dates and times MUST be shown through shared formatters:
  - pesos with thousands separators;
  - dates as MM/DD/YYYY and times as h:mm AM/PM, in the store's time zone.
- **FR-005**: All screens MUST meet WCAG 2.1 AA for contrast, labels and visible focus, and be
  fully keyboard-operable.

**Shell**

- **FR-006**: The sidebar MUST show Home, Sales, Inventory, Services, Customers and Pre-Orders,
  in that order, with icons. POS and Analytics MUST NOT appear until those areas exist.
  "Inventory" opens the Products screen. "Services" opens the Stringing Orders area, whose
  title and records use the "Stringing Orders" term.
- **FR-007**: The header MUST show:
  - the page title and subtitle;
  - a "Synced" or "Offline" pill based on whether the most recent request reached the server;
  - the user badge (initials, display name, role "Admin" for superusers, otherwise "Staff");
  - a Sign out action.
- **FR-008**: Areas not designed yet (Home, Sales, Customers, Pre-Orders, Services) MUST keep
  their placeholder content inside the new shell.

**Products: back office**

- **FR-009**: Products MUST gain optional Model and Supplier fields (text).
- **FR-010**: Every change to a product MUST be recorded in an append-only product history with
  the reason, the staff member and the time. The changes covered are:
  - creation;
  - each edit, with the changed fields' old and new values;
  - deactivation;
  - reactivation.

  Edit, deactivate and reactivate MUST require a non-blank reason. Creation does not.
- **FR-011**: Creating a product MUST accept an optional starting stock. Any starting stock is
  recorded as a restock movement in the same step as the product.
- **FR-012**: Editing a product MAY include a new stock quantity. Any difference is recorded as
  a stock adjustment carrying the edit's reason, in the same step as the other changes. It needs
  the "adjust stock" permission.
- **FR-013**: Edits MUST be refused with a conflict response if the product changed since the
  editor loaded it.
- **FR-014**: Cost price and inventory value MUST only be sent to, and shown to, staff with the
  "view product cost" permission (constitution: cost visibility). Without it, staff can't set or
  change cost.
- **FR-015**: The back office MUST provide the KPI values for the four cards in one request.
- **FR-016**: Each product MUST expose its history (newest first) and its "last updated by" staff
  member.

**Products: screens**

- **FR-017**: The Products screen MUST show the KPI cards, search, filters, the paginated table
  (20 per page, the project default) with Edit and Remove/Reactivate row actions, plus Receive
  Stock and Add Product.
- **FR-018**: The Add and Edit Product forms MUST follow the references' layout and fields, with
  the information banner ("The product appears in POS once saved…" or "Price and stock changes
  are recorded in the audit log…").
- **FR-019**: The Remove Product dialog MUST show the product summary and badge, explain that
  the product is deactivated rather than erased, and require a reason and a confirmation tick.
- **FR-020**: Every save, receive, remove and reactivate MUST end with a confirmation naming the
  product and the result.

### Key Entities

- **Design tokens**: the named colors, type sizes, spacing, radii and shadows.
- **Status badge mapping**: each domain status and its label and style.
- **Product** (extended): adds Model and Supplier, and "last updated by".
- **Product history entry**: append-only. It records:
  - the product;
  - the action (created, updated, deactivated or reactivated);
  - the changed fields, with old and new values;
  - the reason;
  - the staff member;
  - the time.
- **Inventory summary**: the active count, low-stock count, out-of-stock count and inventory
  value at cost.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can add a new product with starting stock in under 60 seconds.
- **SC-002**: Staff can find any product by name or brand within 5 seconds of opening Inventory.
- **SC-003**: Design review finds that the shell, Product List, Add Product, Edit Product and
  Remove Product screens match their references, with no unexplained differences.
- **SC-004**: Automated accessibility checks report zero serious or critical violations on every
  screen in scope.
- **SC-005**: 100% of product edits, stock changes, removals and reactivations appear in the
  product's history with a reason, a staff member and a time.
- **SC-006**: Staff without the cost permission see no cost figures anywhere, and the back office
  sends them none.

## Assumptions

- The Figma references are the design source of truth. Screens without references (Home,
  Customers, Pre-Orders) keep their placeholders.
- Bootstrap stays the base (constitution), restyled through shared tokens. No second UI library
  is added.
- The black circle logo is a placeholder until a real asset is provided.
- The design's product "Category" values (String, Overgrip, Racket, Pickleball, Paddle,
  Shuttlecock) differ from the stored categories. The screens show the stored categories; the
  product type column shows the subcategory when set (for example "String" under Accessories),
  otherwise the category. Changing the category list is a separate decision.
- Cost price stays required when a staff member with the cost permission creates a product. For
  staff without it, products are created with cost 0, to be filled in by a manager.
- The sidebar's "Inventory" opens the Products screen. The current `/products` and `/inventory`
  placeholders merge into one Inventory area.

## Dependencies

- Feature 004: shell, auth, API client, typed modules, QueryState, workAreas.
- Existing catalog and inventory back-office services (restock, adjustment), and the existing
  product `deactivate` and `reactivate` actions. The frontend `productsApi.remove`, which calls
  a rejected DELETE route, is replaced.

## Out of Scope (later features)

- **006 Sales screens**: View, Create, Edit, Cancel Sale; the payment method column; customer
  association.
- **007 Stringing Order screens**: list with chips, create with invoice, details, cancel; string
  color, stencil and grip add-ons, store-string discount.
- **Business-rule features to come**: editing finalized sales, the stock-handling choice when
  cancelling a sale, and "materials used" when cancelling a stringing order.
