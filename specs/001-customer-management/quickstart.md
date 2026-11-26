# Quickstart: Validating Customer Management

How to prove the feature works end to end. Endpoint shapes are in
[contracts/customers-api.md](contracts/customers-api.md); entities and rules are in
[data-model.md](data-model.md).

## Prerequisites

- PostgreSQL running: `docker compose up -d db` (from the repo root).
- `backend/.env` filled in from `backend/.env.example`.
- Dependencies installed in `backend/.venv`.

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/ruff check .
```

The migrations must include: the `phone_normalized` column with its backfill, the
`CustomerAuditEvent` table, the `archive_customer` permission, the full-name check constraint,
and the `PROTECT` changes on `Sale.customer` and `StringingOrder.customer`.

## Automated validation

```bash
.venv/bin/python manage.py test customers sales
```

Expected: all pass. The customers suite must include:

| Test module | Proves |
|---|---|
| `customers/tests/test_phone.py` | Normalization cases: `+63 917…`, `0917-…`, `(02) 8…`, blank, letters |
| `customers/tests/test_services.py` | Create/update validation; archive, reactivate and delete rules; audit events written; delete refused for each history type, including draft sales and cancelled records; `ensure_usable` |
| `customers/tests/test_selectors.py` | Summary totals against hand-computed values (receipts, refunds, voided, cancelled, drafts excluded); net-paid expression equals `Sale.amount_paid` |
| `customers/tests/test_api.py` | Every endpoint's success, 400, 401/403, 404; read-only fields ignored; `status` filter; search by name and phone formats; query counts constant for list, detail and history |
| `customers/tests/test_workflow.py` | Story-level run: create → find → edit → transact → history → archive (blocked from new sale) → reactivate → delete refused; then a no-history customer deleted with an audit event |
| `sales/tests/...` (updated) | `finalize_sale` refuses a draft whose customer was archived |

## Manual smoke test (API)

With the dev server running (`.venv/bin/python manage.py runserver`), sign in through `/admin/`
in the browser (session auth), then use the browsable API:

1. **Create**: POST `/api/customers/` with `{"full_name": "Ana Reyes", "phone_number": "0917 123 4567"}` → `201`, and `duplicate_phone_customers` is `[]`.
2. **Duplicate warning**: POST another customer with `"+63 917-123-4567"` → `201`, and `duplicate_phone_customers` lists Ana.
3. **Search**: GET `/api/customers/?search=ana`, `?search=4567` and `?search=09171234567` → Ana appears in each.
4. **History**: create and finalize a sale for Ana via `/api/sales/` and pay part of it. GET `/api/customers/{id}/` → `summary.sales_count` is 1, and `outstanding_balance` equals the unpaid amount. GET `/api/customers/{id}/sales/` lists the sale.
5. **Archive**: as a user with `archive_customer`, POST `/archive/` → `is_active: false`. GET `/api/customers/` no longer lists Ana; `?status=archived` does. Creating a sale with her `customer_id` → `400`.
6. **Reactivate**: POST `/reactivate/` → Ana is listed again.
7. **Delete refused**: as a user with `delete_customer`, DELETE Ana → `400` (has history).
8. **Delete allowed**: DELETE the second (no-history) customer → `204`. In Django admin (or the shell), a `CustomerAuditEvent` row with `action=DELETED` and the customer's name exists.
9. **Permissions**: as a user with neither permission, archive and delete → `403`.

## Performance check (SC-002, SC-004)

**Required**: run once before merge, and record the timings in the PR:

```bash
.venv/bin/python manage.py shell -c "<seed 20,000 customers and one customer with 500 sales>"
```

Then time `GET /api/customers/?search=…` and `GET /api/customers/{id}/` (e.g. with `curl -w '%{time_total}'`).
Both should be well under 300 ms locally. The automated suite already asserts constant query
counts, which is the regression guard.
