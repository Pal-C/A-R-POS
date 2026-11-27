# Quickstart: Sales Screens

## Prerequisites

- The setup from feature 005's quickstart.
- Run `manage.py migrate`.
- Two staff accounts:
  - **manager**: `sales.record_payment`, `sales.cancel_sale`, `sales.backdate_sale` and
    `catalog.view_product_cost`;
  - **cashier**: `sales.record_payment` only.
- Some active products (including one with stock 1), one inactive product, and a customer
  "Juan Dela Cruz".

## Automated checks (all must pass)

```bash
cd backend && .venv/bin/python manage.py test && .venv/bin/ruff check . && .venv/bin/python manage.py makemigrations --check --dry-run
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Manual validation scenarios

| # | Steps | Expected | Spec |
|---|---|---|---|
| 1 | As the cashier, open Sales, then Create Sale. Link Juan, add 1 × BG66 and 2 × Super Grap, enter a ₱40 discount, choose Cash, enter ₱650 and complete the sale. | A confirmation shows the sale number and a ₱0.00 balance. The sale is listed as Completed, with products "BG66 Ultimax ×1, Super Grap ×2", Cash and today's date. Stock drops by 1 and 2. | US1, US2 |
| 2 | Add a product whose stock is 1, twice | The second Add is disabled | US1-2 |
| 3 | Pay ₱300 of ₱650 | The sale is Pending Payment, and the confirmation shows a ₱350.00 balance | US1-5 |
| 4 | Throttle the network to Slow 3G and double-click Complete | Exactly one sale is created | SC-004 |
| 5 | As the cashier, check the date field | Shows today, read-only | US1-12 |
| 6 | As the manager, pick yesterday's date; then complete without a reason; then complete with a reason | Without a reason the sale is blocked. With one, the sale is listed under yesterday and its history shows "Backdated" with the reason. A future date can't be picked. | US1-11 |
| 7 | Save a draft, leave, then reopen it from the list | The cart is restored. Completing it works. | US3-4 |
| 8 | Open the Pending Payment sale from scenario 3 and record ₱350 GCash | Completed, balance ₱0.00, methods "Cash, GCash" | US3-2 |
| 9 | Open a walk-in sale and choose Associate customer with Ana and a reason | Ana is linked, and the history shows the change | US3-3 |
| 10 | As the manager, cancel the scenario 1 sale with a reason and the confirmation tick | Cancelled. Stock is restored and the refund due is ₱650.00. The sale is still listed, as Cancelled. | US4 |
| 11 | As the cashier, open the sale and the Network tab | No Cancel action. No `unit_cost_price` or `gross_profit` in any response. | US4, FR-012 |
| 12 | Leave Create Sale with items in the cart | A confirmation dialog appears; Stay keeps the cart | Edge |
| 13 | Compare against the Figma PNGs (View Sales, Create, Edit ×2, Cancel) | Matches, apart from the documented differences | SC-006 |
