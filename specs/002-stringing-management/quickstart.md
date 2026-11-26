# Quickstart: Validating Stringing Management

## Prerequisites

- `docker compose up -d db` (PostgreSQL)
- Backend virtualenv active, run from `backend/`
- `python manage.py migrate`

## Automated validation

```bash
cd backend
python manage.py test stringing                # services, models, API, concurrency, report, workflow
python manage.py test sales customers          # regression: payments sync + receipt permission
ruff check . && ruff format --check .
python manage.py makemigrations --check --dry-run
```

Expected: all tests pass, and there are no pending migrations.

## Manual API walkthrough

Use a staff user with `sales.record_payment`, `sales.process_refund`,
`stringing.cancel_stringingorder` and `stringing.view_stringing_financials`, and a second user
with none of them. Requests and responses follow [contracts/stringing-api.md](contracts/stringing-api.md).

1. **Intake** (US1): POST an order for an active customer with price 450 and discount 50. Expect
   `201`, `STR-<year>-NNNNNN`, status RECEIVED, total 400.00, payment state UNPAID. Repeat with no
   customer (walk-in), and with an archived customer (expect `400`).
2. **Unique numbers** (SC-002): run `test_concurrency` in `stringing`. Parallel creates must
   produce distinct numbers.
3. **Workflow** (US2): move the order to IN_PROGRESS and then READY. Try COMPLETED: expect `400`
   with balance 400.00. Try RECEIVED → COMPLETED on another order: expect `400`.
4. **Payments** (US3): record a 150.00 receipt (PARTIAL, balance 250.00). Try 300.00: expect `400`.
   Record 250.00: expect PAID, with `paid_in_full_at` set. Now COMPLETED succeeds.
5. **Search** (US4): search by part of the order number, by a phone in a different format, and
   by "BG80". Filter `status=READY&payment_state=PARTIAL`.
6. **Cancel** (US5): with the user without permission, expect `403`. With a blank reason, expect
   `400`. Cancel a paid order: `refund_due` equals the amount paid. Record a refund with a reason:
   `refund_due` becomes 0.00. A receipt on the cancelled order is refused.
7. **History** (FR-025): GET `/history/`. It shows the create, status, payment, edit and cancel
   entries in order.
8. **Report** (US6): GET the revenue report for today. Only paid-in-full, non-cancelled orders are
   counted, and profit = revenue − cost. With the user without permission, expect `403`, and the
   order details omit `direct_cost` and `profit`.
