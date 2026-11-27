# Contract: Products API changes

Base path: `/api/products/`. Every endpoint requires authentication and returns 401 when the
caller isn't signed in. The conventions are the same as the existing contracts:

- Money is a string.
- Field errors return 400 with field keys.
- A missing record returns 404.
- A missing permission returns 403.

Only the changes are listed here. List, search, ordering and filters are unchanged.

## Product representation

New fields: `model`, `supplier`.

`cost_price` is present **only** when the user has `catalog.view_product_cost`.

The detail view (`GET /api/products/{id}/`) adds `last_event`. It is `null` when the product has
no history yet.

```json
{
  "id": 7, "sku": "YNX-BG66-UM", "name": "BG66 Ultimax", "category": "ACCESSORIES",
  "subcategory": "String", "brand": "Yonex", "model": "BG66 Ultimax", "supplier": "Yonex Philippines",
  "variant_description": "0.68 mm", "description": "",
  "selling_price": "450.00", "cost_price": "320.00",
  "stock_quantity": 89, "low_stock_threshold": 5,
  "is_low_stock": false, "is_out_of_stock": false, "stock_status": "IN_STOCK",
  "is_active": true, "created_at": "…", "updated_at": "…",
  "last_event": {"action": "UPDATED", "performed_by": {"id": 3, "username": "maria", "display_name": "Maria Reyes"}, "created_at": "2026-11-18T08:10:00Z"}
}
```

## POST `/api/products/` (changed)

The request takes the writable fields plus the optional `initial_stock`.

```json
{"sku": "YNX-BG66-UM", "name": "BG66 Ultimax", "category": "ACCESSORIES", "subcategory": "String",
 "brand": "Yonex", "model": "", "supplier": "", "variant_description": "0.68 mm",
 "selling_price": "450.00", "cost_price": "320.00", "low_stock_threshold": 5,
 "is_active": true, "initial_stock": 89}
```

- **Success**: 201 with the product. Its CREATED event and any "Initial stock" RESTOCK movement
  are written in the same transaction.
- **400**: field errors, or `initial_stock < 0`.
- **403**: `cost_price` was sent without `catalog.view_product_cost`. When `cost_price` is left
  out, it defaults to `0.00`.

## PATCH `/api/products/{id}/` (changed)

```json
{
  "changes":  {"selling_price": "480.00", "stock_quantity": 85},
  "expected": {"selling_price": "450.00", "stock_quantity": 89},
  "reason": "Supplier price increase; recount"
}
```

- `changes` can contain any writable field plus `stock_quantity`, but not `is_active`.
  Activation only goes through `deactivate` and `reactivate`, so it gets its own confirmation
  and history entry (code review, 2026-11-27).
- `expected` must hold the value the editor loaded for every key in `changes`.
- `reason` is required.

| Status | When |
|---|---|
| 200 | Product detail returned. One UPDATED event is written. A stock change also writes an ADJUSTMENT_IN or ADJUSTMENT_OUT movement with the same reason. |
| 400 | Field errors; a blank `reason` (`{"reason": ["A reason is required."]}`); an empty `changes`; a key in `changes` that isn't in `expected`; or a SKU that is already taken, including one taken concurrently (`{"sku": [...]}`, never a 500) |
| 403 | `stock_quantity` changed without `catalog.adjust_stock`, or `cost_price` changed without `catalog.view_product_cost` |
| 409 | A changed field's current value differs from `expected`: `{"detail": "This product was changed by someone else.", "current": {"selling_price": "470.00"}}` |

`PUT` isn't supported and returns 405.

## POST `/api/products/{id}/deactivate/` and `/reactivate/` (changed)

The request body is `{"reason": "Discontinued by supplier"}`. The reason is now required and must
be text; a list or object returns 400.

- **Success**: 200 with `{"detail": "...", "product": {...}}`, the same shape as before. A
  DEACTIVATED or REACTIVATED event is written.
- **400**: a blank reason, or the product is already in that state (existing behavior).

## Ordering (changed)

`?ordering=cost_price` and `?ordering=-cost_price` are ignored, falling back to ordering by
name, for users without `catalog.view_product_cost`. Otherwise the cost ranking would leak.

## GET `/api/products/{id}/history/` (new)

The response is paginated, newest first.

```json
{"count": 2, "next": null, "previous": null, "results": [
  {"id": 12, "action": "UPDATED", "changes": {"selling_price": ["450.00", "480.00"], "stock_quantity": [89, 85], "movement_id": 301},
   "reason": "Supplier price increase; recount", "performed_by": {"id": 3, "username": "maria", "display_name": "Maria Reyes"},
   "created_at": "2026-11-27T09:00:00Z"}
]}
```

If the user lacks `catalog.view_product_cost`, `cost_price` entries are removed from `changes`.

## GET `/api/inventory/summary/` (changed)

The response adds `inventory_value` (a Money string), but only for users with
`catalog.view_product_cost`. It is computed over active products.

## Query budgets

| Endpoint | Queries |
|---|---|
| List | 2 (count + page), unchanged |
| Detail | 2 (product + latest event with user) |
| History | 3 (product existence for 404, count, page with `select_related("performed_by")`) |
| Summary | 1 aggregate query |

The tests assert each of these counts.

## Required tests (`backend/catalog/tests/`)

- **Services**:
  - create with and without initial stock;
  - an update writes one event listing only the changed fields;
  - a stock change writes the matching adjustment movement;
  - a conflict on a changed field;
  - no conflict on an unchanged field after a concurrent sale;
  - every permission rule;
  - deactivate and reactivate events;
  - a blank reason is rejected.
- **Model**: the event reason constraint rejects a blank reason on UPDATED.
- **API**: every endpoint above, testing 401, 403, 400, 409 and the success shape. Cost fields
  are hidden without the permission. Query counts are asserted.
- **Concurrency**: two editors change the same field, and the second gets 409. The stock edit
  and a concurrent sale are serialized by the row lock.
