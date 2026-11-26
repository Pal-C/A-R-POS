# Quickstart: Validating Pre-order Management

## Prerequisites

- `docker compose up -d db`
- Run from `backend/` with the virtualenv active, then `python manage.py migrate`

## Automated validation

```bash
cd backend
python manage.py test preorders             # models, services, selectors, API, auth, concurrency, workflow
python manage.py test sales customers       # regression: fulfilled receipts refused, customer summary
ruff check .
python manage.py makemigrations --check --dry-run
```

Expected result: all tests pass and there are no pending migrations.

## Manual API walkthrough

See [contracts/preorders-api.md](contracts/preorders-api.md) for the endpoints.

1. **Create** (US1): create a pre-order for an active customer and product, quantity 2, price
   5,000.00, arriving in 3 weeks.
   - Expect `PO-<year>-NNNNNN`, status PENDING and total 10,000.00.
   - With an archived customer, an inactive product, or a past date, expect `400`.
2. **Deposit** (US2): record a receipt of 4,000.00.
   - Expect state PARTIAL and balance 6,000.00.
   - A receipt of 7,000.00 is refused.
3. **Status and arrival** (US3): move the order to ORDERED, and create a second ORDERED order
   (quantity 1) for the same product.
   - Check `products/{id}/summary/`.
   - POST an arrival with `received_quantity: 2`. The oldest order that fits is marked, and
     `units_left` is reported.
   - POST again choosing the other order by id.
   - Product `stock_quantity` is unchanged.
4. **Fulfill** (US4): fulfilling while money is owed is refused. Pay the balance, then fulfill.
   - Expect FULFILLED, with the user and time recorded.
   - Another receipt is refused.
5. **Search** (US5): search by product SKU and by customer phone. Filter `overdue=true` after
   setting an order's arrival date to the past directly in the database.
6. **Cancel** (US6):
   - Without the permission, expect `403`. With a blank reason, expect `400`.
   - Cancel an order that has a deposit: `refund_due` equals the deposit.
   - Refund it with a reason.
   - A receipt on the cancelled order is refused.
7. **History**: shows each step in order.
