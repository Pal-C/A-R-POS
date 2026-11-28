# Data Model: Stringing Order Screens

The base model is in `specs/002-stringing-management/data-model.md`. Only the changes are
listed here.

## StringingOrder (changed)

| Field | Type | Rules |
|---|---|---|
| `string_color` | Char(50), blank | Trimmed. Free text, e.g. "White". |
| `string_from_store` | Bool, default `False` | The string was bought from the shop. UI label for `discount_amount`. |
| `has_stencil` | Bool, default `False` | |
| `stencil_price` | Decimal(10,2), default 0 | ≥ 0. Must be 0 when `has_stencil` is false. |
| `has_grip` | Bool, default `False` | |
| `grip_price` | Decimal(10,2), default 0 | ≥ 0. Must be 0 when `has_grip` is false. |
| `materials_used` | Bool, null | Set only on cancellation. `null` on non-cancelled orders and on legacy cancellations. |
| `client_transaction_id` | UUID, null, unique | Idempotency key for create. |

`string_type` is unchanged: it is the free-text string model (Q3: C).

### Derived values

- `add_ons_total = stencil_price + grip_price`
- `total_amount = service_price + add_ons_total − discount_amount`. The same formula is used in
  the model property, the `ORDER_TOTAL` query expression, the update check and the revenue
  report.
- `balance`, `refund_due` and `payment_state` are computed as before, from the new total.

### Constraints

| Name | Rule |
|---|---|
| `stringing_addon_prices_nonnegative` | `stencil_price ≥ 0 AND grip_price ≥ 0` |
| `stringing_stencil_price_needs_stencil` | `has_stencil OR stencil_price = 0` |
| `stringing_grip_price_needs_grip` | `has_grip OR grip_price = 0` |
| `stringing_discount_not_above_total` | `discount_amount ≤ service_price + stencil_price + grip_price`. Replaces `stringing_discount_not_above_price`. |
| `stringing_materials_only_when_cancelled` | `status = CANCELLED OR materials_used IS NULL` |
| unique `client_transaction_id` | via `unique=True` (nulls allowed) |

### Migrations

- `0007_order_addons`: adds the fields with defaults, drops the old discount constraint, and adds
  the five constraints above. One migration is enough because the defaults mean "no add-ons":
  every existing row satisfies the constraints and keeps its total.

### Editable fields

`EDITABLE_FIELDS` gains `string_color`, `string_from_store`, `has_stencil`, `stencil_price`,
`has_grip` and `grip_price`. Changes are recorded in the UPDATED event's `changes`, with money
as strings and booleans as is.

## StringingOrderEvent (unchanged schema)

- CANCELLED events now store `changes = {"materials_used": true|false}`.

## Revenue report (changed output)

- New field `gross_add_ons`: the sum of `stencil_price + grip_price` over recognized orders.
- `net_revenue = gross_service_price + gross_add_ons − total_discounts`. The other derived
  totals follow from it.

## Frontend form model (`features/stringing/orderForm.ts`)

```text
OrderFormState {
  customer: CustomerChoice | null
  racket, stringModel, stringColor, tension, notes: string
  servicePrice: string               // pre-filled from config defaults (R2)
  hasStencil, hasGrip, stringFromStore: boolean
  stencilPrice, gripPrice, discount: string
  depositAmount: string; depositMethod: PaymentMethod | ''; depositReference: string
  clientTransactionId: string        // new UUID per form, kept across retries
}
```

**Transitions**:

- Ticking an add-on fills its price with the default if it is empty. Unticking it sends a price
  of 0.
- Ticking store-bought fills the discount with the default if it is 0. Unticking it resets the
  discount to 0.

**`orderTotals(state)`** returns `{service, stencil, grip, discount, total, deposit, balance}`.
Money is handled as BigInt cents.

**`validateOrder(state)`** returns field errors for:

- `racket_description` and `string_type` required;
- money ≥ 0;
- discount ≤ service + add-ons;
- deposit ≤ total;
- a payment method required when the deposit is above 0.

Error keys use the API field names, so server errors land on the same fields.

## Status display (`features/stringing/stringingDisplay.ts`)

- `ALLOWED_MOVES`: RECEIVED → [IN_PROGRESS]; IN_PROGRESS → [READY, RECEIVED];
  READY → [COMPLETED, IN_PROGRESS]. Final statuses have no moves.
- `STEPS = [RECEIVED, IN_PROGRESS, READY, COMPLETED]` for the stepper. CANCELLED shows a
  cancelled banner instead.
- `stringLabel(order)`: "BG80 · White (store-bought) @ 27 lbs". The "@" part is left out when
  the tension is empty.
- `addOnsLabel(order)`: "Stencil, Grip", or "None".
