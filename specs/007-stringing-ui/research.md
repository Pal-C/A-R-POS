# Research: Stringing Order Screens

Decisions for [spec.md](spec.md). Each entry: Decision, Rationale, Alternatives considered.

## R1. Add-ons, colour and store-bought string (FR-021)

**Decision**: add these fields to `StringingOrder`:

| Field | Type | Default |
|---|---|---|
| `string_color` | `CharField(50, blank)` | `""` |
| `has_stencil` | `BooleanField` | `False` |
| `stencil_price` | `DecimalField(10,2)` | `0` |
| `has_grip` | `BooleanField` | `False` |
| `grip_price` | `DecimalField(10,2)` | `0` |
| `string_from_store` | `BooleanField` | `False` |

- The existing `discount_amount` is the store-string discount. The UI labels it "Store-string
  discount" when `string_from_store` is set, and "Discount" otherwise. The backend has always
  allowed a discount without a reason, so this keeps that.
- **Total** becomes `service_price + stencil_price + grip_price − discount_amount`. This one
  formula is used in the model property `total_amount`, the `ORDER_TOTAL` query expression in
  selectors, the update service's "total below paid" check, and the revenue report.
- **New constraints**:
  - an add-on that isn't selected has a price of 0;
  - add-on prices are zero or more;
  - the discount can't exceed service + add-ons. This replaces
    `stringing_discount_not_above_price`.
- **Existing rows** get the defaults, which means "no add-ons", so their totals don't change.
  No backfill is needed.

**Rationale**:

- The clarification asks for stored, reportable fields.
- Storing a flag plus a price keeps the reference's per-line invoice exact, and lets staff
  override a price for one order (Q1).
- The constraint ties the flag and the price together, so a stale price can't hide on an
  unselected add-on.

**Alternatives considered**:

- A generic `StringingAddOn` child table: more flexible, but this needs only two add-ons. It
  would add a join to every list query and a nested write.
- A separate `store_string_discount` field next to `discount_amount`: two discounts would
  confuse the totals and the revenue report.

## R2. Shop default prices (FR-020)

**Decision**: keep the defaults in the frontend `config.ts`, overridable with Vite env variables:

- `VITE_STRINGING_SERVICE_PRICE` = 350.00
- `VITE_STRINGING_STENCIL_PRICE` = 50.00
- `VITE_STRINGING_GRIP_PRICE` = 120.00
- `VITE_STRINGING_STORE_STRING_DISCOUNT` = 100.00

They only pre-fill the Create form. The server stores whatever amounts are submitted and
enforces the rules.

**Rationale**:

- These are pre-fill values, not business rules.
- The server never needs to know them, so a backend settings endpoint would add an endpoint,
  tests and a loading state to the Create screen for no extra safety.

**Alternatives considered**:

- A backend `GET /stringing/defaults/` endpoint driven by Django settings: one source of truth
  for future clients, but more code and a loading state. It can be added later without breaking
  anything.
- An admin-editable settings table: needs a settings screen, which is out of scope.

## R3. Create with deposit, in one idempotent step (FR-009, US1 AS6/AS7)

**Decision**: extend `POST /stringing/orders/` to accept two new optional fields:

- `deposit`: `{amount, payment_method, reference_number?}`;
- `client_transaction_id` (UUID).

A new `take_in_order` service (wrapping the unchanged `create_stringing_order`) then:

1. creates the order;
2. records the deposit through `sales.services.record_payment`, in the same
   `transaction.atomic`.

If any step fails, nothing is saved. A repeated `client_transaction_id` from the same user
returns the existing order with `200` instead of `201`. Any other reuse is refused. A unique
`IntegrityError` from a concurrent retry is resolved the same way as in sales checkout
(006 R1).

- A deposit requires `sales.record_payment`; otherwise the request gets 403.
- The deposit must be `> 0` and `≤ total`.

Because of this, spec US1 AS7 (order saved but deposit failed) can no longer happen. The spec
is updated to say a failed deposit saves nothing.

**Rationale**:

- This is the same pattern already proven in 006's checkout.
- Chaining two calls from the client could leave an unpaid order when the second call fails,
  and a double click could create two orders.

**Alternatives considered**: create, then `POST .../payments/` from the client. This is simpler
on the server, but neither atomic nor idempotent.

## R4. Materials used on cancellation (FR-022)

**Decision**:

- Add `materials_used = BooleanField(null=True)` to `StringingOrder`.
- `POST .../cancel/` now requires `materials_used` (a boolean) next to `reason`. The cancel
  service stores it and adds `{"materials_used": bool}` to the CANCELLED event's `changes`.
- Orders cancelled before this feature keep `null`, and the UI shows "Not recorded".
- New constraint: a non-cancelled order has `materials_used IS NULL`.
- No constraint forces a value on cancelled orders, because legacy rows have none. The
  serializer enforces it for new cancellations.

**Rationale**: the value is stored, shown and audited without rewriting history.

**Alternatives considered**: putting it in the reason text. The clarification (Q2: A) rejected
this.

## R5. Status chip counts (FR-002)

**Decision**: add a new endpoint, `GET /stringing/orders/status-counts/`. It takes the same
query parameters as the list (`search`, `payment_state`, `received_from`, `received_to`,
`customer`). It ignores `status` and returns `{all, RECEIVED, IN_PROGRESS, READY, COMPLETED,
CANCELLED}` from one aggregate query (`Count` with `filter=` per status). `search_orders` is
split so the filtering without `status` can be reused.

**Rationale**:

- A single query keeps counts consistent with the list.
- The alternative of six list requests with `page_size=1` each would multiply round trips and
  query counts.

**Alternatives considered**: putting counts inside the list response. That changes a paginated
contract that other clients (the customer history and the Home placeholder count) rely on.

## R6. Status moves and conflicts (FR-013, FR-014)

**Decision**:

- The client mirrors the backend's `ALLOWED_TRANSITIONS` in `stringingDisplay.ts`, to choose
  which statuses the dropdown offers.
- Each save sends `expected_status`. The backend answers a conflict with
  `400 {detail, current_status}`. The client recognises it by `current_status`, shows the
  backend's message ("…changed by someone else. It is now X.") and refreshes Details.
- Choosing Completed with a balance is blocked on the client with a Record Payment shortcut.
  The server still enforces it.
- A unit test keeps the client map in step with the backend's documented transitions.

**Rationale**: the backend already detects conflicts. Mirroring a small, documented map
avoids an extra endpoint.

**Alternatives considered**: a server-provided `allowed_transitions` field on the detail
response. Cleaner, but it changes the serializer for little gain. Deferred.

## R7. Details as a dialog with an address (spec assumption)

**Decision**: Details is a `Modal` on the list page, opened by `?order=<id>` in the URL.
Closing it removes the parameter and keeps the list's search, chip and page.

- Create (`/stringing/new`), Edit (`/stringing/:id/edit`) and Cancel (`/stringing/:id/cancel`)
  are child pages of the Stringing work area.
- Cancel is guarded by `stringing.cancel_stringingorder`.

**Rationale**:

- This matches the reference (a dialog over the list).
- The order can be linked and survives a reload.
- No nested-route change is needed in the router.

## R8. Frontend structure and reuse

**Decision**:

- **New feature folder** `src/features/stringing/` holds:
  - `StringingOrdersPage`: list, chips, filters, Details host;
  - `OrderDetailsDialog`;
  - `StringingOrderFormPage`: create and edit;
  - `CancelStringingOrderPage`;
  - `StringingPaymentDialog`: a receipt, or a refund on a cancelled order;
  - `InvoicePanel`;
  - `orderForm.ts`: a pure form model with totals and validation, using BigInt-cent money from
    `lib/money.ts`;
  - `stringingDisplay.ts`;
  - `hooks.ts`.
- **Shared pieces** move so both features import them:
  - `CustomerPicker` and `LeaveGuard` go to `src/components/`. `LeaveGuard` gets a `title`
    prop, and `CustomerPicker` takes a `CustomerChoice` type in place of `CartCustomer`, which
    becomes an alias for it.
  - `PAYMENT_METHODS`, `paymentMethodLabel` and `todayInStore` go to `src/lib/payments.ts` and
    `lib/format.ts`. Sales re-imports them, with no behaviour change; the existing sales tests
    cover this.
- **No new dependencies.**

**Rationale**:

- Principle III requires shared components.
- One feature importing another's internals would couple Sales and Services.

## R9. Editing an order (FR-024)

**Decision**: the Create form doubles as Edit for RECEIVED, IN_PROGRESS and READY orders,
using `PATCH` with only the changed fields. Edit doesn't offer a deposit; payments go through
Details. The server already refuses a total below the amount paid. The new fields are added to
`EDITABLE_FIELDS`, so their changes are written to the UPDATED event.

**Rationale**: the backend supports editing, and the reference's edit icon suggests it. Reusing
the form costs little.
