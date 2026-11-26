# Feature Specification: Stringing Management

**Feature Branch**: `002-stringing-management`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Stringing management service: create stringing orders; generate unique order numbers; associate a customer; record racket description; record string type and tension; record service price, discount, and direct cost; update order status; search and filter orders; record partial and full payments; cancel an order with a reason and audit it; calculate stringing revenue and profit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take in a racket for stringing (Priority: P1)

A customer drops off a racket at the counter. Staff create a Stringing Order recording who it is
for (or a walk-in), the racket, the string and tension requested, and the service price, any
discount, and the direct cost of the string used. The system assigns a unique order number that
staff write on the racket tag and give to the customer.

**Why this priority**: Nothing else in stringing works without an order. Intake happens while the
customer waits, so it must be quick.

**Independent Test**: Create an order for an existing customer and one for a walk-in. Each gets a
distinct order number, starts as Received, and shows the entered details and the amount due.

**Acceptance Scenarios**:

1. **Given** the new-order form, **When** staff pick an active customer, enter "Yonex Astrox 88D,
   4U", string "BG80", tension "26 lbs", price 450.00, discount 50.00, direct cost 180.00 and save,
   **Then** the order is created with status Received, a unique order number, a total due of
   400.00, and staff see a confirmation showing the order number.
2. **Given** the form, **When** staff leave the customer empty, **Then** the order is saved as a
   walk-in order.
3. **Given** the form, **When** the racket description or string type is blank, the price is
   negative, the discount is negative or greater than the price, or the direct cost is negative,
   **Then** the order is not saved and each problem is shown next to its field.
4. **Given** an archived customer, **When** staff try to attach them to a new order, **Then** the
   system refuses with a message saying the customer is archived.
5. **Given** two staff members create orders at the same moment, **When** both save, **Then** each
   order receives a different order number.

---

### User Story 2 - Move an order through the workshop (Priority: P1)

Stringers and counter staff update the order status as work progresses: Received → In Progress →
Ready for Pickup → Completed (picked up). Staff can see at a glance which rackets are waiting,
being strung, or ready.

**Why this priority**: The status is how the shop answers "is my racket ready?" and how stringers
know their queue.

**Independent Test**: Take one order through every status in order. Each change is saved, shown on
the order, and recorded with who made it and when. An invalid jump is refused.

**Acceptance Scenarios**:

1. **Given** a Received order, **When** staff mark it In Progress, **Then** the status changes and
   the change is recorded with the user and time.
2. **Given** an In Progress order, **When** staff mark it Ready for Pickup, **Then** the status
   changes and the ready time is recorded.
3. **Given** a Ready for Pickup order with no balance remaining, **When** staff mark it Completed,
   **Then** the status changes and the completion (pickup) time is recorded.
4. **Given** a Ready for Pickup order with an unpaid balance, **When** staff try to mark it
   Completed, **Then** the change is refused with a message showing the balance still owed. Rackets are
   released only when the order is paid in full.
5. **Given** an order was moved forward by mistake (e.g., Ready back to In Progress), **When** staff
   step it back one status, **Then** the change is allowed and recorded. Completed and Cancelled
   orders cannot change status.
6. **Given** an order in any status, **When** staff try to skip ahead (e.g., Received directly to
   Completed), **Then** the change is refused with a message naming the allowed next statuses.

---

### User Story 3 - Take payment, in parts or in full (Priority: P1)

The customer pays a deposit at drop-off and the rest at pickup, or pays everything at once.
Staff record each payment with its amount and method, and the order always shows total due,
amount paid, and balance.

**Why this priority**: Stringing is revenue; the shop must know what each customer has paid and
still owes.

**Independent Test**: On an order with a total of 400.00, record 200.00 cash then 200.00 GCash.
After the first, the balance is 200.00 and the order shows "Partially paid"; after the second, the
balance is 0.00 and the order shows "Paid".

**Acceptance Scenarios**:

1. **Given** an order with a total of 400.00 and nothing paid, **When** staff record 150.00 cash,
   **Then** amount paid is 150.00, balance is 250.00, and payment state is Partially paid.
2. **Given** that order, **When** staff record the remaining 250.00, **Then** balance is 0.00 and
   payment state is Paid.
3. **Given** an order with a balance of 250.00, **When** staff try to record 300.00, **Then** the
   payment is refused because it exceeds the balance.
4. **Given** any order, **When** staff record a zero or negative amount, or omit the payment
   method, **Then** the payment is refused with a field message.
5. **Given** a Cancelled order, **When** staff try to record a new payment, **Then** it is refused.
6. **Given** a recorded payment, **When** anyone views it later, **Then** it shows the amount,
   method, optional reference number, date, and the staff member who received it. Payments cannot
   be edited or deleted.
7. **Given** a payment was recorded on the wrong order, **When** a permitted user corrects it,
   **Then** the correction is made as a refund entry referencing the order, never by editing the
   original payment.

---

### User Story 4 - Find orders (Priority: P2)

Staff search for an order by order number, customer name or phone, racket, or string, and filter
the list by status, payment state, and date range, to answer customer questions or see the
workshop queue.

**Why this priority**: Needed daily, but builds on orders existing.

**Independent Test**: With orders in several statuses and dates, filter to Ready for Pickup and
search by a customer's phone. Only matching orders appear.

**Acceptance Scenarios**:

1. **Given** existing orders, **When** staff search a full or partial order number, **Then** the
   matching order appears.
2. **Given** existing orders, **When** staff search a customer's name or phone (partial, any case,
   ignoring spaces and dashes), **Then** that customer's orders appear.
3. **Given** existing orders, **When** staff search text in the racket description or string type
   (e.g., "BG80"), **Then** orders containing it appear.
4. **Given** the list, **When** staff filter by one or more statuses, by payment state (Unpaid,
   Partially paid, Paid), and/or by a date-received range, **Then** only orders matching all
   chosen filters appear.
5. **Given** more orders than fit on a page, **When** staff view the list, **Then** it is paged,
   newest first by default.
6. **Given** no order matches, **When** the search runs, **Then** staff see a "No stringing orders
   found" message with an action to create one.

---

### User Story 5 - Cancel an order with a reason (Priority: P2)

A customer changes their mind, or an order was created by mistake. A permitted staff member
cancels the order with a written reason. The cancellation is recorded with who did it, when, and
why, and the order remains visible in history.

**Why this priority**: Keeps records honest without deleting anything; less frequent than daily
intake and payment.

**Independent Test**: Cancel an unpaid Received order with reason "Customer changed mind". The
order shows Cancelled, the reason, the user and the time; it no longer counts toward revenue or
outstanding balance; it cannot be changed further.

**Acceptance Scenarios**:

1. **Given** an order that is not Completed or Cancelled, **When** a permitted user cancels it with
   a reason and confirms, **Then** the order becomes Cancelled and records the reason, user and
   time.
2. **Given** the cancel dialog, **When** the reason is blank or whitespace, **Then** the
   cancellation is refused.
3. **Given** a Completed or already Cancelled order, **When** anyone tries to cancel it, **Then** the
   system refuses.
4. **Given** a user without cancel permission, **When** they try to cancel, **Then** the action is
   refused and no cancel option is offered.
5. **Given** an order with money already received, **When** it is cancelled, **Then**
   the order is cancelled immediately, its payments are left unchanged, and the order shows the
   refund due (net amount paid). A permitted user then returns the money with one or more refunds,
   which remain allowed on the cancelled order until the refund due is 0.00.
6. **Given** a Cancelled order, **When** anyone views it or the audit history, **Then** the
   cancellation reason, user and time are shown and cannot be edited.

---

### User Story 6 - See stringing revenue and profit (Priority: P3)

A manager views stringing revenue, direct cost, and profit for a chosen date range, with the
number of orders, to judge how the stringing service is performing.

**Why this priority**: Valuable for management but not needed to serve customers.

**Independent Test**: With four known orders in a date range (two paid in full, one partially
paid, one cancelled), the report shows revenue, cost and profit that match a hand calculation over
the two paid-in-full orders only.

**Acceptance Scenarios**:

1. **Given** orders in a date range, **When** a manager views the stringing report for that range,
   **Then** it shows the count of orders paid in full in the range, gross service price, total discounts, net revenue, total direct
   cost, and profit (net revenue minus direct cost).
2. **Given** the report, **When** a cancelled order falls in the range, **Then** it is excluded from
   revenue, cost and profit, and shown separately as a cancelled count.
3. **Given** the report, **Then** an order's revenue and direct cost are counted on the date
   the order became paid in full, whether or not it has been picked up. Orders that are unpaid or
   only partially paid are not yet counted.
4. **Given** a user without cost/report permission, **When** they try to view the report or any
   order's direct cost or profit, **Then** cost and profit are hidden and the report is refused.
5. **Given** a range with no orders, **When** the report runs, **Then** it shows zeros, not an error.

---

### Edge Cases

- **Order number collisions**: numbers are unique even under simultaneous creation; a failed save
  never leaves a gap that is later reused for a different order.
- **Price changes after intake**: price, discount and direct cost can be corrected while the order
  is not Completed or Cancelled, but never set so that the total due falls below the amount already
  paid. Each change is recorded with who made it, the old and new values, and when.
- **Discount equals price**: a fully discounted (free) order has a total of 0.00 and is
  immediately Paid; it may be completed without any payment.
- **Zero direct cost**: allowed (e.g., customer supplied their own string); profit equals revenue.
- **Tension formats**: tension is recorded as entered (e.g., "24 lbs", "24/26 lbs", "11 kg") and may
  be blank when the customer leaves it to the stringer.
- **Walk-in orders**: orders without a customer are searchable by order number, racket and string,
  and do not appear in any customer's history.
- **Customer archived after intake**: the existing order keeps its customer and can still be
  progressed, paid and completed.
- **Concurrent payments**: two payments recorded at the same moment can never together exceed the
  total due.
- **Concurrent status changes**: if two staff change the status at the same moment, one succeeds and
  the other is refused with the current status shown.
- **Refunds on completed orders**: a refund after pickup reduces amount paid but does not reopen
  the order. The order stays Paid with a balance of 0.00, keeps counting toward revenue on its
  original paid-in-full date, and the refund is reported separately on its refund date (FR-028).
  A completed, fully paid ("settled") order takes no further receipts.
- **Legacy completed orders**: orders completed before this feature without full payment are not
  settled. They keep their real balance, appear as unpaid in the report, and can still be paid;
  once paid in full they count as revenue on that date.
- **Paid in full but cancelled later**: an order that was paid in full and then cancelled is
  excluded from revenue in every period, so a past period's report can go down after a
  cancellation. The cancelled-order count shows why.

### Screen States

Every stringing screen MUST show these four states (constitution Principle III):

| Screen | Loading | Empty | Error | Success |
|---|---|---|---|---|
| Order list / search | Placeholder rows while results load; search and filters stay usable. | "No stringing orders found" plus a "New stringing order" action. | A message that orders could not be loaded, with retry. | Paged list with order number, customer, racket, string, tension, status, total, balance. |
| New / edit order form | Save button shows progress and is disabled. | Not applicable. | Field errors next to each field, or a single alert; typed input is kept. | Confirmation showing the new order number, then the order details. |
| Order details | Placeholder while loading. | Not applicable. | "Order not found" for an unknown order; load error with retry otherwise. | All fields, status timeline, payments, balance, cancellation details if any. |
| Status change | Action shows progress and is disabled. | Not applicable. | Refusal message (invalid transition, changed by someone else). | Confirmation and the updated status. |
| Payment dialog | Confirm button shows progress and is disabled. | Not applicable. | Field errors (amount, method) or refusal (exceeds balance, cancelled order). | Confirmation with new amount paid and balance. |
| Cancel dialog | Confirm button shows progress and is disabled. | Not applicable. | Refusal message (blank reason, wrong status, no permission); dialog stays open. | Confirmation ("Order cancelled"); status badge updates. |
| Revenue & profit report | Placeholder figures while loading. | Zeros for a range with no orders. | Load error with retry; invalid date range message. | Totals for the chosen range. |

## Clarifications

### Session 2026-11-26

- Q: How is stringing revenue counted? → A: On payment: an order counts (net revenue and direct
  cost) once it is paid in full, on the date it became paid in full, even if not yet picked up.
- Q: Can a racket be picked up with money still owed? → A: No. Customers must pay in full before
  rackets are released; marking Completed is refused while a balance remains.
- Q: What happens when an order with money paid is cancelled? → A: Cancel immediately; the order
  shows the refund due and money is returned afterwards with refunds (same as sales).
- Q: (Follow-up after code review) Does a refund on a completed order remove it from revenue? → A:
  No. Completed orders stay counted and settled; post-pickup refunds are listed separately in the
  report by refund date.

## Requirements *(mandatory)*

### Functional Requirements

**Creating orders**

- **FR-001**: Users MUST be able to create a Stringing Order with a required racket description,
  required string type, optional tension, required service price, optional discount (default
  0.00), optional direct cost (default 0.00), optional notes, and an optional customer.
- **FR-002**: The system MUST assign each order a unique, human-readable order number at creation
  (e.g., `STR-2026-000123`). Numbers MUST never be reused or duplicated, including under concurrent
  creation.
- **FR-003**: The system MUST refuse an archived customer on a new order, consistent with the
  existing customer rules.
- **FR-004**: The system MUST reject a blank racket description or string type, a negative price,
  a negative discount, a discount greater than the price, and a negative direct cost, with a
  message tied to the field. All amounts are in pesos with two decimal places.
- **FR-005**: The order total due MUST equal service price minus discount.
- **FR-006**: Every order MUST record who created it and when.

**Editing orders**

- **FR-007**: Users MUST be able to edit the customer, racket description, string type, tension,
  notes, price, discount and direct cost while the order is not Completed or Cancelled, with the
  same validation as creation.
- **FR-008**: An edit MUST NOT reduce the total due below the net amount already paid.
- **FR-009**: Changes to price, discount or direct cost MUST be recorded in the order's audit
  history with old value, new value, user and time.

**Status**

- **FR-010**: Orders MUST have exactly one status: Received, In Progress, Ready for Pickup,
  Completed, or Cancelled. New orders start as Received.
- **FR-011**: Allowed forward transitions are Received → In Progress → Ready for Pickup →
  Completed. A single step back (In Progress → Received, Ready for Pickup → In Progress) is allowed
  to correct mistakes. Completed and Cancelled are final. All other transitions MUST be refused.
- **FR-012**: Each status change MUST be recorded in the order's audit history with the previous
  status, new status, user and time. The times an order became Ready for Pickup and Completed MUST
  be shown on the order.
- **FR-013**: An order MUST NOT be marked Completed while its balance is above 0.00. The refusal
  MUST show the balance still owed.

**Payments**

- **FR-014**: Users with payment permission MUST be able to record a payment on an order that is
  not Cancelled, with amount (greater than 0), method (Cash, GCash, Maya, Bank Transfer, Card,
  Other), optional reference number, and optional notes. The payment records who received it and
  when.
- **FR-015**: A payment MUST NOT make the net amount paid exceed the total due.
- **FR-016**: Each order MUST show amount paid (receipts minus refunds), balance (total due minus
  amount paid), and payment state: Unpaid, Partially paid, or Paid.
- **FR-017**: Payments MUST NOT be edited or deleted. Corrections MUST be refunds that reference
  the order, require refund permission and a reason, and cannot exceed the net amount paid.

**Searching and filtering**

- **FR-018**: Users MUST be able to search orders by partial order number, customer name, customer
  phone (normalized as in customer search), racket description, or string type, case-insensitive.
- **FR-019**: Users MUST be able to filter orders by one or more statuses, by payment state, by
  customer, and by date-received range; filters combine with search.
- **FR-020**: Order lists MUST be paged and sorted newest first by default, with sorting by date
  received and status also available.

**Cancellation and audit**

- **FR-021**: Users with cancel permission MUST be able to cancel an order that is not Completed or
  Cancelled, with a required non-blank reason, after an explicit confirmation step.
- **FR-022**: Cancellation MUST record the reason, user and time; these MUST NOT be editable
  afterwards. Cancelled orders MUST remain visible and searchable.
- **FR-023**: Cancelling MUST NOT change or remove payments. A cancelled order MUST show its refund
  due (net amount paid), and permitted users MUST be able to record refunds against it until the
  refund due is 0.00. No new receipts are allowed on a cancelled order.
- **FR-024**: Orders MUST NOT be deletable.
- **FR-025**: Each order MUST have a viewable audit history listing creation, edits to money
  fields, status changes, payments, refunds and cancellation, in time order.

**Revenue and profit**

- **FR-026**: Permitted users MUST be able to view, for a chosen date range: order count, gross
  service price, total discounts, net revenue, total direct cost, profit (net revenue minus direct
  cost), and cancelled-order count.
- **FR-027**: Cancelled orders MUST be excluded from revenue, cost and profit.
- **FR-028**: An order's net revenue (total due) and direct cost MUST be counted in the report on
  its paid-in-full date: the date of the payment that brought its balance to 0.00 (or its creation
  date if the total due is 0.00). Unpaid and partially paid orders MUST NOT be counted. Before
  pickup, if a refund or edit leaves a balance again, the order stops counting until it is paid in
  full again, and is then counted on the new paid-in-full date. After pickup (Completed), refunds
  do not reopen a balance or remove the order from revenue; instead the report MUST show the total
  of post-pickup refunds dated in the range, plus revenue and profit after those refunds. The report
  MUST also show, separately, the count and outstanding balance of non-cancelled orders not yet
  paid in full.
- **FR-029**: Each order's own profit (total due minus direct cost) MUST be visible to permitted
  users on the order details.

**Access**

- **FR-030**: Only signed-in staff MUST access stringing orders. Recording payments, processing
  refunds, cancelling orders, and viewing direct cost/profit/reports MUST each require a dedicated
  permission. Users without cost permission MUST NOT see direct cost or profit anywhere.

### Key Entities

- **Stringing Order**: a racket stringing job. Order number, optional customer, racket
  description, string type, tension, notes, service price, discount, direct cost, status,
  created by/at, ready at, completed at, and cancellation reason/by/at. Total due, amount paid,
  balance, payment state and profit are derived.
- **Stringing Order Event** (audit history): one entry per creation, money-field edit, status
  change or cancellation, with event type, previous and new values, user and time. Append-only.
- **Payment** (existing, shared with sales and pre-orders): a receipt or refund linked to exactly
  one order, with amount, method, reference, received by, and date. Append-only.
- **Customer** (existing): optional owner of the order; must be active when attached.
- **Stringing Revenue Report** (derived, not stored): totals over a date range.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can create a stringing order for an existing customer in under 45 seconds.
- **SC-002**: 0 duplicate order numbers across 1,000 orders created, including under simultaneous
  creation by multiple staff.
- **SC-003**: Search and filter results appear within 1 second for a store with 50,000 orders.
- **SC-004**: For every order, amount paid and balance always equal the sum of its payments and
  refunds, verified across all orders in acceptance testing (100% match).
- **SC-005**: 100% of cancellations show a reason, user and time; 0 orders can be deleted.
- **SC-006**: The revenue and profit report for any one-month range matches a hand calculation from
  the same orders exactly, and loads within 2 seconds.
- **SC-007**: Staff can answer "is my racket ready and what do I owe?" from the order list in
  under 15 seconds in at least 9 of 10 trials.

## Assumptions

- **Existing building blocks**: the existing Stringing Order record and the shared Payment record
  (receipts and refunds, append-only) are reused and extended rather than replaced.
- **Who can do what**: all signed-in staff can create, view, search, edit and change status.
  Recording payments, refunds, cancelling, and seeing cost/profit/reports need dedicated
  permissions, typically held by managers or cashiers as configured.
- **One racket per order**: an order covers one racket. Several rackets from the same customer are
  separate orders.
- **No stock deduction**: string used is captured as a direct-cost amount only; this feature does
  not deduct string reels from inventory.
- **Order number format**: `STR-<year>-<sequence>`, sequence not resetting per year; exact format can
  be adjusted in planning.
- **Currency**: Philippine pesos, two decimals. No tax handling specific to stringing.
- **Out of scope**: customer notifications (SMS/email when ready), printing racket tags or
  receipts, stringer assignment and workload, string inventory, and combining stringing with a
  product sale in one checkout.
- **Dependencies**: customers feature (active/archived rule, phone normalization) and the shared
  Payment record from sales.
