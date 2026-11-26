# Feature Specification: Pre-order Management

**Feature Branch**: `003-preorder-management`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Pre-order management module: create pre-order; associate customer and product; record quantity and agreed unit price; record expected arrival date; track order status; record deposits and payments; calculate remaining balance; search and filter pre-orders; mark products as arrived; fulfill pre-orders; handle cancellation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take a pre-order with a deposit (Priority: P1)

A customer wants a product the shop doesn't have in stock (e.g., a new racket model). Staff create a
Pre-order for that customer and product, recording the quantity, the agreed unit price, and the
expected arrival date if known. The customer usually leaves a deposit. The system assigns a unique
order number and shows the agreed total, the amount paid and the remaining balance.

**Why this priority**: Every other pre-order action starts from a recorded order and its deposit.
It happens while the customer is at the counter.

**Independent Test**: Create a pre-order for an existing customer and product (quantity 2, agreed
price 5,000.00, expected arrival in 3 weeks) and record a 4,000.00 deposit. The order has a unique
number, status Pending, total 10,000.00, paid 4,000.00 and balance 6,000.00.

**Acceptance Scenarios**:

1. **Given** an active customer and an active product, **When** staff enter quantity 2, agreed unit
   price 5,000.00 and an expected arrival date and save, **Then** the pre-order is created with
   status Pending, a unique order number, total 10,000.00, and staff see a confirmation showing the
   order number.
2. **Given** the new pre-order form, **When** the customer or product is missing, the quantity is
   zero or negative, or the agreed unit price is negative, **Then** the pre-order is not saved and
   each problem is shown next to its field.
3. **Given** an archived customer or an inactive product, **When** staff try to use it on a new
   pre-order, **Then** the system refuses with a message saying which one cannot be used.
4. **Given** the form, **When** staff leave the agreed unit price empty, **Then** it defaults to the
   product's current selling price, which staff can override.
5. **Given** an expected arrival date in the past, **When** staff save, **Then** the order is
   refused with a message next to the date. The date may be left empty when unknown.
6. **Given** two staff members create pre-orders at the same moment, **When** both save, **Then**
   each receives a different order number.

---

### User Story 2 - Record deposits and payments (Priority: P1)

The customer pays a deposit when ordering and the rest later, in one or several payments. Staff
record each payment with its amount and method, and the order always shows total, amount paid and
remaining balance.

**Why this priority**: Deposits are the shop's protection against unclaimed special orders, and the
balance must be known when the customer collects.

**Independent Test**: On a 10,000.00 pre-order, record 4,000.00 (cash), then 6,000.00 (GCash).
After the first, balance is 6,000.00 and payment state Partially paid; after the second, balance is
0.00 and payment state Paid.

**Acceptance Scenarios**:

1. **Given** a pre-order with total 10,000.00 and nothing paid, **When** staff record 4,000.00,
   **Then** amount paid is 4,000.00, balance 6,000.00, and payment state Partially paid.
2. **Given** a balance of 6,000.00, **When** staff try to record 7,000.00, **Then** the payment is
   refused because it exceeds the balance.
3. **Given** any pre-order, **When** staff record a zero or negative amount or omit the method,
   **Then** the payment is refused with a field message.
4. **Given** a Fulfilled or Cancelled pre-order, **When** staff try to record a new payment, **Then**
   it is refused.
5. **Given** recorded payments, **When** anyone views the order, **Then** each payment shows amount,
   method, optional reference number, date, and who received it. Payments cannot be edited or
   deleted; corrections are refunds with a reason.

---

### User Story 3 - Track status from order to arrival (Priority: P1)

Staff move a pre-order through its stages: Pending (taken from the customer) → Ordered from
Supplier → Arrived. When stock arrives, staff mark the product as arrived, which marks the waiting
pre-orders for that product as Arrived so staff know whom to contact.

**Why this priority**: The status answers "has my racket arrived?" and tells staff which customers
to call.

**Independent Test**: Two pre-orders for the same product are Ordered. Staff mark 3 units of the
product as arrived. Both pre-orders (quantities 1 and 2) become Arrived, with the arrival time
recorded.

**Acceptance Scenarios**:

1. **Given** a Pending pre-order, **When** staff mark it Ordered from Supplier, **Then** the status
   changes and the change is recorded with user and time.
2. **Given** pre-orders for a product, **When** staff mark that product as arrived with a received
   quantity, **Then** by default the oldest Ordered pre-orders for that product are marked Arrived
   first, each only if its full quantity still fits in the units received; the rest stay Ordered.
   Alternatively, staff pick which Ordered pre-orders to mark from the product's waiting list, as
   long as their total quantity does not exceed the units received. Either way, staff see which
   orders were marked and how many units are left over.
3. **Given** an Ordered pre-order, **When** staff mark that single pre-order Arrived, **Then** its
   status changes and the arrival time is recorded.
4. **Given** an order moved forward by mistake, **When** staff step it back one status (Arrived →
   Ordered, Ordered → Pending), **Then** the change is allowed and recorded. Fulfilled and Cancelled
   are final.
5. **Given** an expected arrival date changes, **When** staff update it, **Then** the new date is
   saved and the change recorded.
6. **Given** pre-orders whose expected arrival date has passed and that have not arrived, **When**
   staff filter for overdue pre-orders, **Then** they appear.

---

### User Story 4 - Fulfill a pre-order (Priority: P1)

When the customer collects, staff fulfill the pre-order: the customer has paid in full, the goods
are handed over, and the order is closed.

**Why this priority**: Closing the order is when the shop actually completes the sale.

**Independent Test**: An Arrived pre-order paid in full is fulfilled; its status becomes Fulfilled
with the time and user recorded, and stock is not changed. An Arrived pre-order with a balance cannot be
fulfilled.

**Acceptance Scenarios**:

1. **Given** an Arrived pre-order with balance 0.00, **When** staff fulfill it and confirm, **Then**
   status becomes Fulfilled and the fulfillment time and user are recorded.
2. **Given** an Arrived pre-order with a balance, **When** staff try to fulfill it, **Then** it is
   refused with a message showing the balance owed.
3. **Given** a Pending or Ordered pre-order, **When** staff try to fulfill it, **Then** it is refused
   because the goods have not arrived.
4. **Given** any pre-order action (arrival, fulfillment, cancellation), **Then** product stock is
   not changed: pre-ordered goods go straight from the supplier delivery to the customer and never
   count as shelf stock.

---

### User Story 5 - Find pre-orders (Priority: P2)

Staff search pre-orders by order number, customer name or phone, or product name or SKU, and filter
by status, payment state, product, customer, expected arrival range, and overdue.

**Why this priority**: Needed daily to answer customer questions and to plan supplier orders, but
builds on orders existing.

**Independent Test**: With pre-orders in several statuses, filter status Ordered and product X: only
those pre-orders appear, paged, newest first.

**Acceptance Scenarios**:

1. **Given** existing pre-orders, **When** staff search a partial order number, a customer name or
   phone (any format), or a product name or SKU, **Then** matching pre-orders appear.
2. **Given** the list, **When** staff combine filters (one or more statuses, payment state, product,
   customer, expected-arrival date range, overdue only), **Then** only orders matching all filters
   appear.
3. **Given** more results than fit a page, **When** staff view the list, **Then** it is paged, newest
   first by default, with sorting by expected arrival date available.
4. **Given** no matches, **When** the search runs, **Then** staff see "No pre-orders found" with an
   action to create one.
5. **Given** a product, **When** staff view its open pre-orders, **Then** they see how many units are
   waiting per status, to decide how many to order from the supplier.

---

### User Story 6 - Cancel a pre-order (Priority: P2)

A customer changes their mind, or the supplier cannot deliver. A permitted staff member cancels the
pre-order with a reason; the cancellation is recorded and the order stays in history.

**Why this priority**: Less frequent than daily intake and payments, but needed to keep records and
money right.

**Independent Test**: Cancel a pre-order with a 4,000.00 deposit and reason "Supplier discontinued".
The order shows Cancelled with reason, user and time, the refund due is 4,000.00, and no further
changes are allowed except refunds.

**Acceptance Scenarios**:

1. **Given** a pre-order that is not Fulfilled or Cancelled, **When** a permitted user cancels it
   with a reason and confirms, **Then** it becomes Cancelled and records reason, user and time.
2. **Given** a blank reason, a Fulfilled or Cancelled order, or a user without cancel permission,
   **When** they try to cancel, **Then** the system refuses.
3. **Given** an order with money paid, **When** it is cancelled, **Then** it is cancelled
   immediately, its payments are left unchanged, and it shows the refund due (net amount paid). A
   permitted user then returns the money with one or more refunds, which remain allowed until the
   refund due is 0.00. No new receipts are allowed.
4. **Given** a Cancelled pre-order, **When** anyone views it, **Then** the cancellation reason, user
   and time are shown and cannot be edited.

---

### Edge Cases

- **Order number collisions**: numbers are unique even under simultaneous creation and are never
  reused.
- **Price changes after ordering**: the agreed unit price is locked once any payment is recorded,
  except that a permitted user may correct it, as long as the new total is not below the amount
  already paid. Every change is recorded with old and new values.
- **Quantity changes**: allowed while Pending or Ordered, with the same "not below amount paid"
  rule; not allowed once Arrived.
- **Product price changes in the catalog** do not change existing pre-orders: the agreed price is
  fixed at order time.
- **Product deactivated after ordering**: existing pre-orders continue and can be fulfilled.
- **Customer archived after ordering**: existing pre-orders continue; the archive warning (customers
  feature) already lists open pre-orders.
- **Zero-price pre-order** (e.g., a free promotional item): total 0.00, immediately Paid.
- **Concurrent payments**: two payments at the same moment can never together exceed the total.
- **Concurrent status changes**: one succeeds; the other is refused with the current status shown.
- **Arrival with fewer units than waiting**: pre-orders not covered stay Ordered. With the default
  oldest-first rule, a large older order that doesn't fit is skipped and a smaller newer one may be
  marked; staff see which ones.
- **Arrival with more units than waiting**: all waiting orders are marked; the leftover units are
  reported so staff can add them to stock separately through the inventory module.
- **No Ordered pre-orders for the product**: marking arrived reports "No pre-orders waiting for this
  product" and changes nothing.

### Screen States

Every pre-order screen MUST show these four states (constitution Principle III):

| Screen | Loading | Empty | Error | Success |
|---|---|---|---|---|
| Pre-order list / search | Placeholder rows; search and filters stay usable. | "No pre-orders found" plus "New pre-order". | Load error with retry. | Paged list: number, customer, product, quantity, total, paid, balance, status, expected arrival (overdue highlighted). |
| New / edit form | Save button shows progress and is disabled. | Not applicable. | Field errors or a single alert; input kept. | Confirmation with order number, then details. |
| Pre-order details | Placeholder while loading. | Not applicable. | "Pre-order not found"; load error with retry. | Fields, status history, payments, balance, cancellation details. |
| Status change / mark arrived | Action shows progress and is disabled. | "No pre-orders waiting for this product" when marking arrived. | Refusal message (invalid transition, changed by someone else). | Confirmation with updated status (and which orders were marked arrived). |
| Payment dialog | Confirm shows progress and is disabled. | Not applicable. | Field errors or refusal (exceeds balance, closed order). | Confirmation with new paid amount and balance. |
| Fulfill dialog | Confirm shows progress and is disabled. | Not applicable. | Refusal (balance owed, not arrived, stock). | Confirmation "Pre-order fulfilled". |
| Cancel dialog | Confirm shows progress and is disabled. | Not applicable. | Refusal (blank reason, wrong status, no permission); dialog stays open. | Confirmation "Pre-order cancelled"; status badge updates. |

## Clarifications

### Session 2026-11-26

- Q: How do pre-orders affect stock? → A: They never touch stock; pre-ordered goods go straight from
  the supplier delivery to the customer.
- Q: What happens to money paid on a cancelled pre-order? → A: Cancel immediately; the order shows
  the refund due and money is returned afterwards with refunds (same as sales and stringing).
- Q: When a delivery arrives, which pre-orders get marked Arrived? → A: Oldest Ordered pre-orders
  first when their full quantity fits (default), or staff pick specific Ordered pre-orders whose
  total fits the units received.

## Requirements *(mandatory)*

### Functional Requirements

**Creating and editing**

- **FR-001**: Users MUST be able to create a pre-order with a required customer, required product,
  required quantity (whole number ≥ 1), agreed unit price (≥ 0.00; defaults to the product's
  current selling price), optional expected arrival date (today or later), and optional notes.
- **FR-002**: The system MUST assign each pre-order a unique, human-readable order number at
  creation, never reused, including under concurrent creation.
- **FR-003**: The system MUST refuse archived customers and inactive products on new pre-orders.
- **FR-004**: The pre-order total MUST equal quantity × agreed unit price.
- **FR-005**: Users MUST be able to edit quantity, agreed unit price, expected arrival date and notes
  while the order is Pending or Ordered (expected arrival date and notes also while Arrived). An
  edit MUST NOT make the total less than the net amount already paid. Changing the agreed unit price
  after any payment requires the price-override permission.
- **FR-006**: Every pre-order MUST record who created it and when.

**Status**

- **FR-007**: Pre-orders MUST have exactly one status: Pending, Ordered from Supplier, Arrived,
  Fulfilled, or Cancelled. New pre-orders start as Pending.
- **FR-008**: Allowed transitions: Pending → Ordered → Arrived → Fulfilled, plus one step back
  (Ordered → Pending, Arrived → Ordered) to correct mistakes. Fulfilled and Cancelled are final.
  All other transitions MUST be refused.
- **FR-009**: Users MUST be able to mark a product as arrived with a received quantity (≥ 1). By
  default the system marks that product's Ordered pre-orders as Arrived, oldest first, skipping any
  whose full quantity no longer fits in the remaining units. Alternatively users MUST be able to
  select specific Ordered pre-orders of that product, whose total quantity must not exceed the units
  received. The result MUST list the orders marked and the units left over.
- **FR-010**: The times an order was marked Ordered, Arrived and Fulfilled MUST be recorded and shown.
- **FR-011**: A pre-order whose expected arrival date is before today and that is still Pending or
  Ordered MUST be flagged as overdue.

**Payments**

- **FR-012**: Users with payment permission MUST be able to record payments (deposits and later
  payments) on pre-orders that are not Fulfilled or Cancelled, with amount (> 0), method, optional
  reference number and notes. Each payment records who received it and when.
- **FR-013**: A payment MUST NOT make the net amount paid exceed the total.
- **FR-014**: Each pre-order MUST show amount paid (receipts minus refunds), remaining balance
  (total minus amount paid), and payment state: Unpaid, Partially paid, or Paid.
- **FR-015**: Payments MUST NOT be edited or deleted; corrections are refunds with a reason and
  refund permission, never exceeding the net amount paid.

**Fulfillment**

- **FR-016**: Users MUST be able to fulfill a pre-order only when it is Arrived and its balance is
  0.00, after an explicit confirmation step. Fulfillment records the time and user.
- **FR-017**: Pre-orders MUST NOT change product stock at any point (arrival, fulfillment or
  cancellation).

**Searching and filtering**

- **FR-018**: Users MUST be able to search by partial order number, customer name, customer phone
  (normalized as in customer search), product name, or SKU, case-insensitive.
- **FR-019**: Users MUST be able to filter by one or more statuses, payment state, customer, product,
  expected arrival date range, and overdue only; filters combine with search.
- **FR-020**: Lists MUST be paged, newest first by default, with sorting by expected arrival date.
- **FR-021**: Users MUST be able to see, per product, the number of units on open pre-orders by
  status (Pending, Ordered, Arrived).

**Cancellation and audit**

- **FR-022**: Users with cancel permission MUST be able to cancel a pre-order that is not Fulfilled
  or Cancelled, with a required reason and an explicit confirmation step. The reason, user and time
  MUST be recorded and not editable.
- **FR-023**: Cancelling MUST NOT change or remove payments. A cancelled pre-order MUST show its
  refund due (net amount paid), and permitted users MUST be able to record refunds against it until
  the refund due is 0.00. No new receipts are allowed on a cancelled pre-order.
- **FR-024**: Pre-orders MUST NOT be deletable.
- **FR-025**: Each pre-order MUST have a viewable history of creation, edits, status changes,
  payments, refunds, fulfillment and cancellation, in time order.

**Access**

- **FR-026**: Only signed-in staff MUST access pre-orders. Recording payments, processing refunds,
  cancelling, and overriding the agreed price after payment MUST each require a dedicated
  permission.

### Key Entities

- **Pre-order**: a customer's order for a product not yet in hand. Order number, customer, product,
  quantity, agreed unit price, expected arrival date, notes, status, created by/at, ordered at,
  arrived at, fulfilled at/by, cancellation reason/by/at. Total, amount paid, balance, payment state
  and overdue are derived.
- **Pre-order Event** (audit history): one entry per creation, edit, status change, arrival,
  fulfillment or cancellation, with previous and new values, user and time. Append-only.
- **Payment** (existing, shared with sales and stringing): receipts and refunds linked to exactly one
  order. Append-only.
- **Customer** and **Product** (existing): must be active when attached.
- **Inventory movement** (existing): not affected by pre-orders.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can create a pre-order with a deposit for an existing customer and product in
  under 60 seconds.
- **SC-002**: 0 duplicate order numbers across 1,000 pre-orders, including simultaneous creation.
- **SC-003**: Search and filter results appear within 1 second for 20,000 pre-orders.
- **SC-004**: For every pre-order, amount paid and balance equal the sum of its payments and refunds
  (100% match in acceptance testing).
- **SC-005**: When stock arrives, staff can mark all waiting pre-orders for that product in one
  action, taking under 30 seconds.
- **SC-006**: 0 pre-orders can be fulfilled with a balance owed or before arrival.
- **SC-007**: 100% of cancellations show reason, user and time; 0 pre-orders can be deleted.

## Assumptions

- **Existing building blocks**: the existing Pre-order record, the shared Payment record (receipts and
  refunds, append-only) and the customer and product records are reused and extended. The stringing
  feature's patterns (order numbering, audit events, permissions, payment state) are followed.
- **One product per pre-order**: several products mean several pre-orders.
- **Who can do what**: all signed-in staff can create, view, search, edit, change status, mark
  arrived and fulfill. Payments, refunds, cancellation and price overrides after payment need
  dedicated permissions.
- **Full payment before handover**: as with stringing, goods are released only when paid in full.
- **No supplier records**: "Ordered from Supplier" is a status only; purchase orders, suppliers and
  supplier costs are out of scope.
- **No notifications**: SMS or email to customers on arrival is out of scope; staff use the
  customer's phone from the order.
- **Currency**: Philippine pesos, two decimals.
- **Out of scope**: revenue/profit reporting for pre-orders, partial fulfillment of a single
  pre-order (several units handed over at different times), and combining a pre-order with a sale
  in one checkout.
- **Dependencies**: customers feature (active rule, phone search), catalog products (active flag,
  selling price), sales Payment services. Inventory is not involved.
