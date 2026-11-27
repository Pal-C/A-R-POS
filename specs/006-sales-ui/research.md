# Research: Sales Screens

## R1. One-step checkout (FR-004, SC-003, SC-004)

- **Decision**: a new service, `sales.services.checkout_sale`, exposed as
  `POST /api/sales/checkout/`. In one `transaction.atomic` block it:
  1. creates the draft, or replaces an existing draft's cart when `draft_id` is given;
  2. finalizes the sale (stock deducted, sale number assigned, `sale_date` set);
  3. records the optional receipt;
  4. writes a BACKDATED event when a backdate was applied.
- **Idempotency**: the request carries a client-generated `client_transaction_id` (UUID). The
  model already has a unique field with that name, so a repeated request returns the existing
  sale with 200 instead of creating another one. The frontend generates one ID per cart and
  keeps it across retries.
- **Rationale**: the existing endpoints would need three calls (create, finalize, pay). If the
  second or third failed, a draft or an unpaid finalized sale would be left behind. One
  transaction makes the result all or nothing, as Principle I requires.
- **Checkout-path impact** (Principle IV): the work is the same as the existing create, finalize
  and pay calls, but in one round trip instead of three, so it is faster than before. Product
  rows are still locked in primary-key order. The query count is asserted in a test.

## R2. Drafts (FR-010)

- **Decision**: `PUT /api/sales/{id}/draft/` replaces a draft's cart in one call (items,
  customer, discount) through a new service, `replace_draft_cart`. New drafts use the existing
  `POST /api/sales/`. Checkout accepts `draft_id` to finalize a draft with its latest cart.
- **Rationale**: the client cart is the source of truth while editing. Replacing the whole cart
  avoids error-prone item-by-item syncing. The existing per-item endpoints stay for other
  clients.

## R3. Date of sale and backdating (FR-005, FR-005a)

- **Decision**:
  - Add `Sale.sale_date`, a `DateField` holding the store-local business date. It is null while
    the sale is a draft.
  - `finalize_sale` sets it to today's local date.
  - Checkout accepts `sale_date` and `backdate_reason`. A date earlier than today requires the
    new permission `sales.backdate_sale` and a non-blank reason. A future date returns 400.
  - `finalized_at` keeps the real time, for audit.
  - A data migration backfills `sale_date` from the local date of `finalized_at` on existing
    finalized sales.
  - A check constraint requires a `sale_date` on every sale that isn't a draft.
  - The list orders by `sale_date` descending (drafts first), then `-created_at`. A new index
    covers `(-sale_date, -created_at)`.
- **Rationale**: this keeps the real and business timelines separate, and the history records
  every backdate. The date has no time part because the reference shows a date-only field.

## R4. Sale history (FR-009, FR-005a)

- **Decision**: a new append-only model, `sales.SaleEvent`:
  - `sale` (FK, PROTECT);
  - `action` (TextChoices `CUSTOMER_CHANGED` and `BACKDATED`);
  - `changes` (JSON);
  - `reason`, non-blank by database constraint;
  - `performed_by` (FK, PROTECT);
  - `created_at`.

  A new service, `change_sale_customer`, links or changes the customer on PENDING_PAYMENT and
  COMPLETED sales only. It runs `ensure_usable` on the customer, locks the row, and writes the
  event. It is exposed as `POST /api/sales/{id}/customer/`.
- **Rationale**: the same audit pattern as `ProductEvent` and `StringingOrderEvent`. Drafts keep
  using `update_draft_sale`, which needs no history.

## R5. List data without extra queries per row (FR-002)

- **Decision**: `SaleListSerializer` gains:
  - `items_summary`, e.g. "BG66 Ultimax ×1, Super Grap ×2";
  - `payment_methods`: the distinct methods of posted receipts, in order;
  - `sale_date`.

  The list queryset prefetches `items__product` and `payments` and uses
  `select_related(customer, created_by)`. The list endpoint uses a fixed 4 queries (count, page,
  items with products, payments), asserted in a test.

## R6. Cost visibility in sales (FR-012)

- **Decision**: `SaleItemSerializer.to_representation` drops `unit_cost_price` and
  `gross_profit` unless `can_view_cost(request)` is true. That function is imported from
  `catalog.serializers`. Every sales response is built with the request in its context;
  `sale_detail_response` and the views are updated to pass it.

## R7. Client-side money arithmetic (FR-006)

- **Decision**: `src/lib/money.ts` provides:
  - `toCents(Money) → bigint`;
  - `fromCents(bigint) → Money`;
  - `addMoney`, `subtractMoney` and `multiplyMoney(Money, qty)`;
  - `compareMoney`.

  The cart totals use these only; no floats are involved.

## R8. Frontend structure

| Route | Screen |
|---|---|
| `/sales` | Sales list |
| `/sales/new` | Create Sale |
| `/sales/:id` | Sale details. A draft opens in the editor instead. |
| `/sales/:id/cancel` | Cancel Sale (requires the cancel permission) |

- **New feature components** in `src/features/sales/`:
  - `ProductPicker`: search plus a paginated grid of product cards;
  - `Cart`: lines, quantity stepper, remove, and the totals panel;
  - `CustomerPicker`: search by name or phone, or create a new customer inline;
  - `PaymentFields`;
  - `SaleSummary`;
  - `RecordPaymentDialog` and `AssociateCustomerDialog`.
- **State**: the cart is a reducer (`cartReducer.ts`, unit-tested). Unsaved changes are guarded
  with react-router's `useBlocker`, which shows a confirmation `Modal`, not a browser dialog.
- **Rationale**: the cart has many interacting rules (stock caps, merging lines, totals), which
  suit a pure, testable reducer.

## R9. Out of scope, recorded as follow-ups

- The `sales.finalize_sale` and `sales.apply_sale_discount` permissions exist but aren't
  enforced by the existing views. This predates the feature and isn't changed here.
- The customer sales history still orders by `finalized_at`. Showing `sale_date` there is a
  follow-up.
