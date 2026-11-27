# Data Model: Design System, App Shell and Products Screens

## Backend

### Product (extended), `catalog.Product`

| Field | Type | Rules |
|---|---|---|
| `model` | CharField(100), blank | new; trimmed |
| `supplier` | CharField(150), blank | new; trimmed |

All other fields are unchanged:

- sku, name, category, subcategory, brand, variant_description, description;
- selling_price, cost_price;
- stock_quantity, low_stock_threshold;
- is_active;
- timestamps.

`stock_quantity` stays read-only on the serializer and changes only through inventory services.

**Migration**: `catalog/migrations/00NN_product_model_supplier_productevent.py` adds both fields
with default `""` and creates `ProductEvent`. It doesn't backfill events for existing products:
their history starts empty, and "last updated by" shows "—".

### ProductEvent (new), `catalog.ProductEvent`

This table is append-only. There is no update or delete path, and the admin is read-only.

| Field | Type | Rules |
|---|---|---|
| `id` | PK | |
| `product` | FK Product, `on_delete=PROTECT`, `related_name="events"` | |
| `action` | CharField, TextChoices `CREATED`, `UPDATED`, `DEACTIVATED`, `REACTIVATED` | |
| `changes` | JSONField, default `{}` | `{field: [old, new]}`. Decimals are stored as strings. A stock change also has `"movement_id"`. |
| `reason` | TextField, blank | |
| `performed_by` | FK User, `on_delete=PROTECT` | |
| `created_at` | DateTimeField, `auto_now_add` | |

**Constraints**:

- `CheckConstraint`: `action == "CREATED" OR length(trim(reason)) > 0`. It is named
  `productevent_reason_required`.
- Index on `(product, -created_at)`.

### Inventory summary, `GET /api/inventory/summary/` (extended)

| Field | Type | Notes |
|---|---|---|
| `active_product_count` | int | existing |
| `total_units_in_stock` | int | existing |
| `low_stock_count` | int | existing (active, 0 < stock ≤ threshold) |
| `out_of_stock_count` | int | existing (active, stock = 0) |
| `inventory_value` | Money string | **new**; Σ cost × stock over active products. Present only with `catalog.view_product_cost`. |

### Validation rules (services)

- `name` must not be blank after trimming. `sku` must be unique, case-insensitive. Both are
  existing rules.
- Prices must be ≥ 0. This is an existing rule, also enforced by a database constraint.
- `low_stock_threshold` must be ≥ 0.
- `initial_stock` must be ≥ 0.
- `stock_quantity` on update must be ≥ 0. A change needs `catalog.adjust_stock`.
- `cost_price` in the input needs `catalog.view_product_cost`; otherwise the request gets 403.
- `reason` is required, non-blank, for update, deactivate and reactivate. If it is missing, the
  response is 400 `{"reason": [...]}`.
- `expected[field]` must equal the current value for every changed field. Otherwise the response
  is 409 `{"detail": "...", "current": {field: value}}`.

## Frontend (client-side types)

### Design tokens (`src/styles/_tokens.scss`)

The named colors, type and spacing are listed in [research R1](research.md#r1-theming-bootstrap-to-match-the-references-fr-001-fr-002).

### StatusBadgeSpec (`src/lib/statusBadges.ts`)

```ts
type BadgeTone = 'outline' | 'navy' | 'sky' | 'yellow' | 'black' | 'muted'
interface StatusBadgeSpec { label: string; tone: BadgeTone }
```

| Domain | Value | Label | Tone |
|---|---|---|---|
| stock | `IN_STOCK` | In Stock | outline |
| stock | `LOW_STOCK` | Low Stock | yellow |
| stock | `OUT_OF_STOCK` | Out of Stock | black |
| product | active / inactive | Active / Inactive | navy / muted |
| sale | `DRAFT` | Draft | outline |
| sale | `PENDING_PAYMENT` | Pending Payment | yellow |
| sale | `COMPLETED` | Completed | navy |
| sale | `CANCELLED` | Cancelled | black |
| stringing | `RECEIVED` | Received | outline |
| stringing | `IN_PROGRESS` | In Progress | sky |
| stringing | `READY` | Ready for Pickup | yellow |
| stringing | `COMPLETED` | Completed | navy |
| stringing | `CANCELLED` | Cancelled | black |
| preorder | `PENDING` | Pending | outline |
| preorder | `ORDERED` | Ordered from Supplier | sky |
| preorder | `ARRIVED` | Arrived | yellow |
| preorder | `FULFILLED` | Fulfilled | navy |
| preorder | `CANCELLED` | Cancelled | black |

### WorkArea (extended)

| Field | Type | Notes |
|---|---|---|
| `navLabel` | string | sidebar text, e.g. "Services" |
| `title`, `subtitle` | string | page header, e.g. "Stringing Orders" / "Track, update and search racket stringing orders" |
| `icon` | `LucideIcon` | |
| `children` | `{ path, title, subtitle, load }[]` | sub-pages, e.g. `new`, `:id/edit` |

### ConnectionStatus (`src/lib/connection.ts`)

`'online' | 'offline'`. The initial value is `navigator.onLine ? 'online' : 'offline'`.

### ProductFormValues

All values are strings, so inputs stay controlled and money never passes through a float.

| Field | Shown on |
|---|---|
| `name`, `category`, `brand`, `model`, `variant_description`, `supplier` | both |
| `cost_price`, `selling_price` | both (cost only with permission) |
| `stock_quantity` | both (edit: only with `catalog.adjust_stock`) |
| `low_stock_threshold`, `sku`, `is_active` | both |
| `reason` | edit only |

### Toast

`{ id, tone: 'success' | 'error', message }`. A toast closes itself after 5 s, and stays open
while hovered or focused.
