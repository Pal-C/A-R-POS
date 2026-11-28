# Feature Specification: Stringing Order Screens

**Feature Branch**: `007-stringing-ui`

**Created**: 2026-11-28

**Status**: Draft

**Input**: User description: "Let's do the frontend for the stringing orders. Use these images as
references and tailor them to the backend as you see fit." The four references are:

- **SO Home**: the Stringing Orders list
- **SO Details**: the order details dialog with a status stepper
- **Create SO**: Create a Stringing Order, with an invoice panel
- **Cancel SO**: Cancel Stringing Order

## Overview

This feature replaces the Services (Stringing Orders) placeholder with working screens. It uses
the design system, app shell, and patterns from features 005 (Inventory) and 006 (Sales). Staff
can:

- browse, search and filter stringing orders by status;
- take in a racket as a new order, linked to a customer or left as a walk-in, and take an
  optional deposit;
- open an order to see its details and money breakdown, move it along the workflow
  (Received → In Progress → Ready for Pickup → Completed), and collect the balance;
- cancel an order with a reason.

The stringing backend (feature 002) already provides orders, the status workflow, payments,
refunds, cancellation and history. The references show some details that the backend does not
store today:

- string colour;
- add-ons (stencil, grip) priced as separate lines;
- a "string bought from store" discount;
- a "materials used" choice on cancellation;
- a payment method attached to the order itself.

Colour, add-ons, store-bought and materials used become new stored fields, prices come from shop defaults that staff can override, and the payment method stays on payments (see Clarifications and FR-020 to FR-024).

### Reference vs backend adaptations (decided)

| Reference shows | Adapted to |
|---|---|
| Order IDs like `SO-0126` | The backend order number (e.g. `STR-2026-000126`) is shown as is. |
| Free-text Customer Name + Contact # | A customer picker (search by name or contact number, or create a customer on the spot), as in Create Sale. Leaving it empty makes a walk-in order. The contact number shown is the linked customer's. |
| Payment method on the order | The payment method belongs to the deposit payment. It is asked for only when a deposit is entered, and listed per payment in Details. |
| "Deposit paid" in the breakdown | The order's net amount paid (receipts minus refunds). |
| Status dropdown with every status | Only the moves the workflow allows from the current status (one step forward or back). Cancelled is never in the dropdown; it has its own action. |
| Completing an order | Allowed only when the balance is ₱0.00. Details offers to record the remaining payment first. |
| Date column (11/20) | Date received (order creation date). |

## Clarifications

### Session 2026-11-28

- Q: Where do the stringing prices come from? → A: Shop defaults (₱350 service, ₱50 stencil,
  ₱120 grip, −₱100 store-string discount) are pre-filled on each new order, and staff can
  override any of them for that order.
- Q: How are string colour, add-ons, "string bought from store" and "materials used" stored? →
  A: As proper stored fields on the order (a backend change), so Details shows them exactly and
  they can be filtered and reported on later.
- Q: Where does the string model come from? → A: Typed freely by staff. No link to inventory
  and no stock change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take in a racket (Priority: P1)

At the counter, staff:

1. click **New Order** on Stringing Orders;
2. optionally link a customer, found by name or contact number or created on the spot;
3. enter the racket model, string model, string colour and tension;
4. tick add-ons (stencil, grip) and "string bought from store" if they apply;
5. watch the Invoice panel show the service price, add-ons, discount, total and balance;
6. optionally enter a deposit with its payment method;
7. click **Create Order**.

The app confirms the new order number and shows the order with status Received.

**Why this priority**: Taking in rackets is the daily core of the stringing service. Without it,
no order exists to track.

**Independent Test**: Link "Juan Dela Cruz", enter Arcsaber 11, BG80, 27 lbs, tick Stencil and
String bought from store, enter a ₱270 GCash deposit, and create the order.

- A new order number is shown and the order is Received.
- Its total, amount paid (₱270) and balance match the Invoice panel.
- It appears at the top of the Stringing Orders list.

**Acceptance Scenarios**:

1. **Given** the Create screen, **When** staff tick or untick an add-on or the store-string box,
   **Then** the Invoice panel updates at once (within 100 ms as perceived).
2. **Given** an empty racket model or string model, **When** staff click Create Order, **Then**
   the error shows next to the field and nothing is saved.
3. **Given** a deposit above the total, or negative, **When** staff click Create Order, **Then**
   the error shows next to the deposit field and nothing is saved.
4. **Given** a deposit above ₱0, **When** no payment method is chosen, **Then** Create Order is
   refused with a message next to the payment method.
5. **Given** no customer is linked, **When** the order is created, **Then** it is a walk-in order.
6. **Given** a network failure or a double click on Create Order, **When** the order is
   submitted, **Then** at most one order is recorded.
7. **Given** recording the deposit fails (e.g. the payment is refused), **When** staff click
   Create Order, **Then** neither the order nor the deposit is saved, the error is shown, and the
   form keeps its input.
8. **Given** staff without the "record payment" permission, **When** they open the Create
   screen, **Then** the deposit fields are not offered.
9. **Given** unsaved input, **When** staff click Cancel or navigate away, **Then** they are asked
   to confirm leaving.

---

### User Story 2 - Browse and find orders (Priority: P1)

Staff open **Services** and see Stringing Orders: a searchable, paginated table with status
chips showing counts (All, Received, In Progress, Ready for Pickup, Completed, Cancelled). Each
row shows:

- order number;
- customer (or "Walk-in");
- racket;
- string / tension, e.g. "BG66 Ultimax @ 26 lbs";
- date received;
- status badge;
- balance;
- actions: open details, and cancel (for orders that can still be cancelled, by staff allowed to).

**Why this priority**: Staff need to answer "is my racket ready?" and find orders to work on.

**Independent Test**: With seeded orders, click the "Ready for Pickup" chip, search "Mika", and
page through. The rows, counts and pages are correct.

**Acceptance Scenarios**:

1. **Given** orders exist, **When** the screen opens, **Then** the newest orders appear first,
   with the All chip selected.
2. **Given** a status chip, **When** clicked, **Then** the list shows only that status, and each
   chip shows how many orders match the current search.
3. **Given** a search by order number, customer name, contact number, racket or string, **When**
   typed, **Then** the list updates after a short pause.
4. **Given** the Filter button, **When** staff set a received-date range or a payment state
   (unpaid / partially paid / paid), **Then** the list narrows and the active filters are shown
   with a way to clear them.
5. **Given** any search, chip, filter or page, **When** applied, **Then** it is kept in the
   address so the view survives a reload and can be bookmarked.
6. **Given** no orders, or none matching, **When** the list is empty, **Then** the right empty
   state offers "New order" or "Clear filters".
7. **Given** a Completed or Cancelled order, **When** its row is shown, **Then** its cancel
   action is not offered.

---

### User Story 3 - Update progress and hand over (Priority: P1)

From the list, staff open an order's **Details**. They see:

- the order number and status badge;
- a stepper (Received — In Progress — Ready for Pickup — Completed) with the current step marked;
- customer, contact number, racket, date received, string, tension, add-ons and notes;
- the money breakdown: stringing service, add-ons, store-string discount, total, amount paid
  and balance due;
- the payments received.

They pick the next status and click **Save Status**. At pickup they record the remaining payment
and mark the order Completed.

**Why this priority**: Status tracking is how staff and customers know a racket is ready, and
completion is when the shop gets paid.

**Independent Test**: Open an In Progress order with a ₱150 balance.

1. Move it to Ready for Pickup.
2. Try to move it to Completed: it is refused because ₱150 is still due, and staff are offered
   Record Payment.
3. Record ₱150 cash, then complete it. The status is Completed and the balance ₱0.00.

**Acceptance Scenarios**:

1. **Given** an order, **When** Details opens, **Then** the status choices are only the moves the
   workflow allows from the current status.
2. **Given** someone else changed the order's status meanwhile, **When** staff save a status,
   **Then** they are told the current status and Details refreshes; nothing is overwritten.
3. **Given** a balance above ₱0, **When** staff choose Completed, **Then** they are told the
   balance must be paid first and offered Record Payment.
4. **Given** a balance, **When** staff record a payment not exceeding it, **Then** the amount
   paid, balance and list row update.
5. **Given** a Completed or Cancelled order, **When** Details opens, **Then** no status change
   is offered and the order is read only. A Cancelled order shows who cancelled it, when, and
   the reason.
6. **Given** staff without the record-payment or cancel permission, **When** they view Details,
   **Then** those actions are not offered.
7. **Given** a saved status change, **When** Details closes, **Then** the list row and chip
   counts reflect the new status without a manual reload.

---

### User Story 4 - Cancel an order (Priority: P2)

Staff with the cancel permission open **Cancel Stringing Order** from a row's cancel action or
from Details. The screen shows:

- the order summary (number, customer | racket | string @ tension | date, status, amount paid);
- a required reason;
- the materials choice (no materials used yet / materials already used);
- a notice that the cancellation, reason and their name are saved to the audit log, and the
  order is never erased;
- the confirmation box: "I understand this order will be marked Cancelled".

On confirm, the order is cancelled. If money was received, the confirmation shows the amount
that may be refunded, and staff with the refund permission can record the refund from Details.

**Why this priority**: Cancellations are less common than intake but must be safe and auditable.

**Independent Test**: Cancel an In Progress order with a ₱270 deposit, reason "Customer changed
mind", no materials used.

- The order shows Cancelled, with the reason, staff name and time in Details.
- The ₱270 is shown as refundable, and recording a ₱270 refund leaves ₱0 refundable.

**Acceptance Scenarios**:

1. **Given** an empty reason or an unticked confirmation box, **When** staff click Confirm
   Cancellation, **Then** nothing is saved and the missing input is pointed out.
2. **Given** an order that became Completed or Cancelled meanwhile, **When** staff confirm,
   **Then** they are told it can no longer be cancelled and returned to the list.
3. **Given** staff without the cancel permission, **When** they open the cancel address
   directly, **Then** they see the access-denied page.
4. **Given** Back, **When** clicked, **Then** staff return to where they came from without
   changes.

---

### Edge Cases

- A linked customer who has since been deactivated: the order still shows their name and contact
  number. They cannot be picked for a new order.
- Very long racket or string names are truncated in the table, with the full text on hover.
- A tension left empty shows the string alone (no "@").
- An order with a ₱0 total (e.g. a free restring) is paid in full on creation and can be
  completed straight from Ready for Pickup.
- A refund recorded after pickup does not reopen a balance on a Completed order.
- The list shows the stored balance; a cancelled order shows its refundable amount, not a balance.
- Losing the connection mid-save shows the shared connection-error message and keeps the form
  input.

## Requirements *(mandatory)*

### Functional Requirements

**List**

- **FR-001**: The Services area MUST show the Stringing Orders list in place of the placeholder,
  newest first, paginated, with a "Showing X–Y of Z orders" footer.
- **FR-002**: The list MUST offer status chips (All, Received, In Progress, Ready for Pickup,
  Completed, Cancelled), each showing its count for the current search and filters.
- **FR-003**: The list MUST support search by order number, customer name, contact number, racket
  and string, and a Filter panel with a received-date range and a payment state.
- **FR-004**: Search, chip, filters and page MUST be kept in the address.
- **FR-005**: Status badges MUST use the app-wide status colours: Received (outlined), In Progress
  (light blue), Ready for Pickup (yellow), Completed (navy), Cancelled (black).
- **FR-006**: Each row MUST offer an open-details action, and a cancel action only when the order
  can be cancelled and the user holds the cancel permission.

**Create**

- **FR-007**: The Create screen MUST collect: an optional customer (picker with on-the-spot
  creation), racket model (required), string model (required), string colour, tension, add-ons
  (stencil, grip), "string bought from store", optional notes, and an optional deposit with
  payment method.
- **FR-008**: The Invoice panel MUST show the stringing service price, each ticked add-on, the
  store-string discount, the total, the deposit and the balance due, recalculated on every change.
- **FR-009**: Creating MUST save the order and record the deposit (if any) as a payment together:
  both are saved or neither is. Retries and double clicks MUST NOT duplicate either.
- **FR-010**: The screen MUST say that a unique order number is assigned on creation and that
  the status starts as Received.
- **FR-011**: Field errors returned by the system MUST be shown next to the matching field.

**Details and status**

- **FR-012**: Details MUST show the fields listed in User Story 3, the payments received, and for
  cancelled orders the cancellation reason, staff member and time.
- **FR-013**: The status choice MUST list only the moves allowed from the current status. Saving
  MUST send the status the user saw, so a conflicting change is detected and reported instead of
  overwritten.
- **FR-014**: Moving to Completed with a balance above ₱0 MUST be refused with the balance named
  and a Record Payment shortcut.
- **FR-015**: Details MUST let staff with the record-payment permission record a payment (amount
  up to the balance, method, optional reference), and staff with the refund permission record a
  refund on a cancelled order with money received.
- **FR-016**: Direct cost and profit MUST appear only for staff with the stringing financials
  permission.

**Cancel**

- **FR-017**: The Cancel screen MUST require a reason and the confirmation box, and MUST be
  guarded by the cancel permission.
- **FR-018**: After cancelling, staff MUST see the order as Cancelled and, if money was received,
  the refundable amount.

**Consistency**

- **FR-019**: After any save (create, status, payment, cancel), the list, chip counts and Details
  MUST reflect the change without a manual reload.

**Reference details the backend does not store yet**

- **FR-020**: A new order MUST be pre-filled with the shop default prices: ₱350.00 stringing
  service, ₱50.00 stencil, ₱120.00 grip, and a ₱100.00 store-string discount. Staff MUST be able
  to override each of these amounts for that order. Every amount MUST be zero or more, and the
  discount MUST NOT exceed the stringing service price plus add-ons.
- **FR-021**: String colour, the stencil and grip add-ons (each with its own price), and "string
  bought from store" MUST be stored as their own fields on the order. They MUST be shown in
  Details and editable on non-final orders, with changes recorded in the order's history. The
  order's total MUST equal service price + add-on prices − discount. Existing orders without
  these fields MUST show no add-ons, no colour, and not store-bought.
- **FR-022**: The "materials used" choice on cancellation MUST be required and stored with the
  cancellation (alongside the reason, staff member and time), shown in Details for cancelled
  orders, and recorded in the order's history.
- **FR-023**: The string model MUST be typed freely by staff. It has no link to inventory, and
  creating an order never changes stock.
- **FR-024**: Racket, string, tension and customer of a non-final order MAY be edited from
  Details (the backend supports it); editing is limited to non-final orders and every change is
  recorded in the order's history.

### Key Entities

- **Stringing Order**: number, optional customer, racket, string, tension, notes, service price,
  discount, total, amount paid, balance, refundable amount, payment state, status, dates
  (received, ready, completed, cancelled), created by, cancellation reason and staff.
- **Order Payment**: a receipt or refund against an order, with amount, method, reference, date
  and staff member.
- **Customer**: name and contact number; optional on an order.
- **Status workflow**: Received ⇄ In Progress ⇄ Ready for Pickup → Completed (balance ₱0 only);
  any non-final status → Cancelled (reason required). Completed and Cancelled are final.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can take in a racket (customer, racket, string, tension, add-ons, deposit) in
  under 90 seconds.
- **SC-002**: Staff can find any order by number, customer name or contact number in under 10
  seconds.
- **SC-003**: Moving an order one status step takes no more than 3 clicks from the list.
- **SC-004**: No order can be completed with a balance due, and no status change silently
  overwrites another staff member's change.
- **SC-005**: Every cancellation shows a reason, a staff member and a time; no order is ever
  removed.
- **SC-006**: Invoice totals on the Create screen always match the saved order's total and
  balance.

## Assumptions

- Staff are signed in. Viewing, creating and updating orders need only sign-in. Cancelling,
  recording payments, refunds and seeing financials need the existing permissions.
- The list's Date column is the date received; there is no separate due date.
- Status chip counts are fetched per status for the current search and filters; the backend's
  list already supports this.
- No change is made to the status workflow or payment rules of feature 002. The backend gains the order fields of FR-021, the cancellation's materials-used flag (FR-022), and the shop default prices (FR-020); the cancellation rules are otherwise unchanged.
- The Create screen is a page (as in the reference); Details is a dialog over the list, with its
  own address so it can be linked and reloaded; Cancel is a page.
- The reference's "Synced" pill, user badge and sidebar are the existing app shell.
- Printing a claim slip or receipt is out of scope.
