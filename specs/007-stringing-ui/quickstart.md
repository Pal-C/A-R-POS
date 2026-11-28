# Quickstart: Stringing Order Screens

## Prerequisites

- The setup from feature 005's quickstart.
- Run `manage.py migrate`. This applies stringing migration 0007.
- Two staff accounts:
  - **manager**: `stringing.cancel_stringingorder`, `sales.record_payment`,
    `sales.process_refund` and `stringing.view_stringing_financials`;
  - **stringer**: no extra permissions.
- A customer "Juan Dela Cruz" (0917 555 0123), and a few seeded orders in each status.
- Optionally, override the default prices with the `VITE_STRINGING_*` env variables
  ([research R2](research.md#r2-shop-default-prices-fr-020)).

## Automated checks (all must pass)

```bash
cd backend && .venv/bin/python manage.py test && .venv/bin/ruff check . && .venv/bin/python manage.py makemigrations --check --dry-run
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Manual validation scenarios

| # | Steps | Expected | Spec |
|---|---|---|---|
| 1 | As the manager, open Services, then New Order. Link Juan, enter Arcsaber 11 / BG80 / White / 27 lbs, tick Stencil and String bought from store, enter ₱270 GCash and click Create Order. | The Invoice panel shows ₱350 + ₱50 − ₱100 = ₱300 and a ₱30 balance. A confirmation names the new order number. The order is Received with ₱270 paid and a ₱30 balance, and is first in the list. | US1 |
| 2 | Untick and tick Grip, and change its price to ₱100 | The Invoice panel updates at once, and the total follows the override | US1-1, FR-020 |
| 3 | Leave Racket empty and click Create Order; enter a deposit above the total; enter a deposit with no method | The error shows next to each field, and nothing is saved | US1-2..4 |
| 4 | Throttle to Slow 3G and double-click Create Order | Exactly one order and one payment exist | US1-6 |
| 5 | As the stringer, open New Order | No deposit fields are shown | US1-8 |
| 6 | Click the Ready for Pickup chip, search "Juan", then reload the page | The filtered list and chip counts survive the reload | US2 |
| 7 | Filter by received date range and Unpaid | The list narrows, and the active filters can be cleared | US2-4 |
| 8 | Open the scenario 1 order's Details and move it through In Progress and then Ready for Pickup | The stepper and badge update, and so do the list row and the counts | US3 |
| 9 | Choose Completed while ₱30 is due | Refused, naming ₱30, with a Record Payment shortcut. Record ₱30 cash, then complete: the order is Completed with a ₱0.00 balance. | US3-3, US3-4 |
| 10 | Open Details in two tabs; change the status in one, then save in the other | The second tab reports the new status and refreshes | US3-2 |
| 11 | As the manager, cancel an In Progress order that has a deposit: tick "Materials already used", leave the reason empty, then fill it in and confirm | Without a reason it is blocked. With one: Cancelled, with the refundable amount shown. Details shows the reason, the staff member, the time, and "Materials already used". | US4 |
| 12 | Record a refund for the full amount from Details | ₱0 left to refund | US4, FR-015 |
| 13 | As the stringer, open `/stringing/<id>/cancel` | The access-denied page | US4-3 |
| 14 | Edit a Received order: untick Stencil and change the tension | Saved, and the history shows the changes | FR-024 |
| 15 | Compare against the reference PNGs (SO Home, SO Details, Create SO, Cancel SO) | Matches, apart from the adaptations documented in the spec | — |
