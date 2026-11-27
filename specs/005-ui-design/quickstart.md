# Quickstart: Design System, App Shell and Products Screens

## Prerequisites

- The same setup as [feature 004's quickstart](../004-frontend-foundation/quickstart.md).
- Run the migrations: `cd backend && .venv/bin/python manage.py migrate`.
- Two staff accounts:
  - **manager**: has `catalog.view_product_cost` and `catalog.adjust_stock`.
  - **cashier**: has neither permission.
- A handful of products, including at least one at low stock, one out of stock and one inactive.

## Automated checks (all must pass)

```bash
cd backend && .venv/bin/python manage.py test && .venv/bin/ruff check .
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

- The main JS chunk must stay at or under 300 KB gzipped.
- The test run includes the axe checks: no serious or critical violations.

## Manual validation scenarios

| # | Steps | Expected | Spec |
|---|---|---|---|
| 1 | Sign in and visit every sidebar item | Items in order: Home, Sales, Inventory, Services, Customers, Pre-Orders. No POS or Analytics. The active item is sky with a yellow bar. The header title and subtitle change per area. "Services" opens "Stringing Orders". | US1-1, FR-006 |
| 2 | Stop the backend and click around, then restart it | The pill shows "Offline", then "Synced" again after the next request | US1-2 |
| 3 | Resize to 900 px | The sidebar shows icons only, with tooltips. No horizontal scroll. | US1-4 |
| 4 | Keyboard only: tab through Inventory, open and close Remove with Escape | "Skip to content" appears first. Focus is always visible, the dialog traps focus, and focus returns to the Remove button. | US1-5, FR-005 |
| 5 | Compare the shell, Product List, Add, Edit and Remove against the Figma PNGs side by side | Layout, colors, type and components match. Note any differences. | SC-003 |
| 6 | As the manager, open Inventory | The KPI values match the data, including Inventory Value at cost | US2-1 |
| 7 | As the cashier, open Inventory and Edit | No Inventory Value card, no cost field, Stock read-only. In the Network tab, no `cost_price` in any response. | US2-2, SC-006 |
| 8 | Search "BG66", filter Low Stock, go to page 2 | Correct rows; the "Showing X–Y of N" text is correct | US2-3 |
| 9 | Add a product with starting stock 89 | It is listed as In Stock with 89, and a toast confirms it. Its history and inventory movements show the starting stock. | US3-1 |
| 10 | Edit the price and stock (89 → 85) with a reason | Saved, with one history entry for both changes, and the inventory shows an ADJUSTMENT_OUT of 4 | US3-3 |
| 11 | Open Edit in two tabs and change the price in both | The second save shows "changed by someone else" with the current value | US3-6 |
| 12 | Receive 10 units | Stock +10, a toast shows the new level | US4-1 |
| 13 | Remove a product (the button is disabled until a reason is entered and the box ticked), then reactivate it | Deactivated and shown as Inactive under the filter; reactivated. Both appear in the history with their reasons. | US4-2..4 |
| 14 | Contrast check with browser devtools on the badges, buttons and sidebar | All AA | FR-005 |
