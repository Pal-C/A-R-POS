# Data Model: Sales Screens

## Backend

### Sale (extended)

| Field | Type | Rules |
|---|---|---|
| `sale_date` | DateField, null | Store-local business date. Null for drafts; set at finalization. May be earlier than today only with `sales.backdate_sale` and a reason; never later than today. |

- **Meta.permissions**: adds `("backdate_sale", "Can record sales with a past date")`.
- **Constraint**: `sale_date_required_when_finalized`, i.e. `status = 'DRAFT' OR sale_date IS NOT NULL`.
- **Index**: `(-sale_date, -created_at)`.
- **Migrations**:
  1. `0006_sale_sale_date_saleevent`: adds the field, the index, the permission and the
     `SaleEvent` model.
  2. `0007_backfill_sale_date`: sets `sale_date` to the store-local date of `finalized_at`, or
     of `created_at` if `finalized_at` is null, for every sale that isn't a draft.
  3. `0008_sale_date_constraint`: adds the constraint.

### SaleEvent (new, append-only)

| Field | Type | Rules |
|---|---|---|
| `sale` | FK Sale, PROTECT, `related_name="events"` | |
| `action` | TextChoices `CUSTOMER_CHANGED`, `BACKDATED` | |
| `changes` | JSON | CUSTOMER_CHANGED: `{"customer": [old_id or null, new_id]}`. BACKDATED: `{"sale_date": [today, chosen]}` |
| `reason` | Text | Must be non-blank (constraint `saleevent_reason_required`) |
| `performed_by` | FK User, PROTECT | |
| `created_at` | DateTime, auto | |

The admin view is read-only. Events are ordered oldest first.

### Service rules

| Service | Rules |
|---|---|
| `checkout_sale` | Items must be non-empty, with no duplicate products. Each product must be active and have enough stock, checked inside the transaction under row locks. The discount must be 0 or more and no more than the remaining total. The payment amount must be at least 0.01 and no more than the total. The customer must be usable. The date and its reason follow R3. The `client_transaction_id` is unique, and a repeat returns the existing sale. |
| `replace_draft_cart` | The sale must be a draft. Item and discount rules are the same as checkout. Prices are snapshotted again at the current price. |
| `change_sale_customer` | The sale must be PENDING_PAYMENT or COMPLETED. The customer must be usable and different from the current one. A reason is required. |

## Frontend

### CartState (`features/sales/cartReducer.ts`)

```ts
interface CartLine { productId: number; name: string; type: string; unitPrice: Money; quantity: number; available: number }
interface CartState {
  lines: CartLine[]
  discount: Money          // sale-level, "0.00" default
  customer: CustomerListItem | null
  paymentMethod: PaymentMethod | ''
  amountPaid: Money | ''
  saleDate: string         // YYYY-MM-DD, defaults to today (store TZ)
  backdateReason: string
  clientTransactionId: string // crypto.randomUUID(), regenerated only after a successful checkout
}
```

**Actions**:

- `add(product)`: adds 1, merging into an existing line and capped at the available stock.
- `setQuantity(productId, n)`: n must be 1 or more and no more than the available stock.
- `remove(productId)`.
- `setDiscount`, `setCustomer`, `setPayment`, `setDate`.
- `load(draft)`: fills the cart from a saved draft.
- `reset`.

**Derived values** (`cartTotals`): `subtotal`, `discount`, `total`, `balance` (total minus
amount paid). All are Money strings, computed through `lib/money.ts`.

### Validation (client, mirrors the server)

- The cart must have at least one line.
- The discount must be 0 or more and no more than the subtotal.
- If a payment method is chosen, the amount must be at least 0.01 and no more than the total.
- The amount can be empty, meaning no payment now.
- The sale date can't be in the future. A date before today requires a reason.
