# Feature Specification: Sales Screens

**Feature Branch**: `006-sales-ui`

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "Do the sales UI". The Figma references are the following screens,
shared during feature 005:

- View Sales
- Create Sale (with customer association)
- Edit Sale, with and without customer association
- Cancel Sale

## Clarifications

### Session 2026-11-27

- Q: How much of a finalized sale can be edited? → A: Only the customer can be linked or
  changed on a finalized sale, with a reason recorded in the sale's history. Everything else on
  a finalized sale is read only. Full editing (cart, customer, discount) works on draft sales
  only.
- Q: Can staff record a sale with a past date? → A: Yes, but only staff with a new "backdate
  sales" permission. A reason is required, the date can't be in the future, and the backdating
  is recorded in the sale's history.

## Overview

This feature builds the Sales area on the design system and components from feature 005. Staff
can:

- browse and search sales;
- ring up a new sale from a grid of product cards into a cart;
- take a full or partial payment;
- link the sale to a customer, or leave it as a walk-in;
- open a sale to see its details, collect a remaining balance, or cancel it with a reason.

It also closes the cost-exposure gap carried over from 005: sale lines currently show unit cost
and gross profit to every staff member.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ring up a sale (Priority: P1)

At the counter, staff:

1. open **Create Sale** and optionally link a customer, found by name or contact number, or
   created on the spot;
2. search the product grid and click **Add** on product cards to fill the cart;
3. adjust quantities and an optional discount, watching the subtotal, discount and total due
   update instantly;
4. choose a payment method and enter the amount paid;
5. complete the sale.

The app then shows the sale number, the status (Completed, or Pending Payment when a balance
remains), and any outstanding balance.

**Why this priority**: This is the shop's main daily task, and the reason the POS exists.

**Independent Test**: Link "Juan Dela Cruz", add 1 × BG66 Ultimax (₱450) and 2 × Super Grap
(₱120), take a ₱40 discount, and pay ₱650 cash.

- The sale completes with a new sale number and a balance of ₱0.00.
- Stock drops by 1 and 2.
- The sale appears in the Sales list as Completed.

**Acceptance Scenarios**:

1. **Given** the Create Sale screen, **When** staff click Add on a product card, **Then** the
   product enters the cart with quantity 1. Adding it again increases the quantity. The totals
   update at once, within 100 ms as perceived.
2. **Given** a product whose stock is 0, or whose cart quantity already equals its stock,
   **When** it is shown, **Then** its Add button is disabled and the card says so.
3. **Given** a cart, **When** staff change a quantity or remove a line, **Then** the totals
   update. A quantity above the available stock is refused with a message.
4. **Given** a discount larger than the subtotal, or a negative amount, **When** staff try to
   complete the sale, **Then** the error shows next to the field and nothing is saved.
5. **Given** an amount paid lower than the total, **When** the sale completes, **Then** it is
   saved as Pending Payment, and the confirmation shows the balance still owed.
6. **Given** an amount paid higher than the total, **When** staff try to complete the sale,
   **Then** they are told the amount exceeds the total. Change is not tracked by the system:
   staff enter only the amount kept.
7. **Given** a product sold out by someone else while it sat in the cart, **When** staff
   complete the sale, **Then** the sale is not saved, the short product is named, and the cart
   is kept so staff can adjust it.
8. **Given** a network failure or a double click on Complete, **When** the sale is submitted,
   **Then** at most one sale is recorded.
9. **Given** staff who lack the "record payment" permission, **When** they open Create Sale,
   **Then** the payment fields are not offered. The sale completes as Pending Payment for
   someone with the permission to collect.
10. **Given** a cart and no customer, **When** the sale completes, **Then** it is recorded as a
    walk-in sale.
11. **Given** staff with the "backdate sales" permission, **When** they pick an earlier date of
    sale, **Then** a reason is required. The sale is listed under that date and its history
    records the backdating. A future date is refused, and "Set to today" restores today.
12. **Given** staff without that permission, **When** they open Create Sale, **Then** the date of
    sale shows today, read only.

---

### User Story 2 - Browse and find sales (Priority: P1)

Staff open **Sales** and see a searchable, filterable, paginated table with these columns:

- sale number;
- products summary;
- total;
- payment method(s);
- date;
- status badge.

They can search by sale number or customer name and filter by status. Clicking a row opens the
sale.

**Why this priority**: Staff need this to answer customer questions ("did I pay for this?") and
to find a sale to cancel or collect.

**Independent Test**: With seeded sales, search "S-0142", filter Pending Payment, and page
through the results. The columns show the right products, totals, methods and dates.

**Acceptance Scenarios**:

1. **Given** sales exist, **When** the Sales screen opens, **Then** the newest sales appear
   first. Each row shows:
   - the number;
   - a products summary, e.g. "BG66 Ultimax ×1, Super Grap ×2", truncated with the full text
     on hover;
   - the total;
   - the payment method(s) received, e.g. "Cash", "Cash, GCash", or "—" if unpaid;
   - the date of sale;
   - the status.
2. **Given** a search or status filter, **When** applied, **Then** the list, count and pages
   update, and the filters are kept in the address so the view can be bookmarked.
3. **Given** no sales, or none matching, **When** the list is empty, **Then** the right empty
   state appears, offering "Create sale" or "Clear filters".

---

### User Story 3 - View a sale, collect a balance, link a customer (Priority: P2)

Opening a sale shows its details:

- the sale number and status badge;
- "Recorded <date, time> by <name>";
- the customer, or the "Walk-in sale. No customer is linked." notice;
- the lines, with subtotal, discount, total due, amount paid and outstanding balance;
- the payments received.

From here staff can:

- record a payment toward a balance;
- link a customer to a walk-in sale (or change the linked customer), giving a reason;
- start a cancellation.

**Why this priority**: Pending Payment sales must be collectable. The references show a
customer being associated after the sale.

**Independent Test**:

1. Open a Pending Payment sale with a ₱150 balance and record ₱150 GCash. The sale becomes
   Completed with a ₱0.00 balance.
2. Open a walk-in sale, link "Ana Reyes" with a reason. The sale shows Ana as its customer, and
   the change is recorded with the reason, the staff member and the time.

**Acceptance Scenarios**:

1. **Given** a finalized sale, **When** it is opened, **Then** every detail above is shown, read
   only. Items, prices and discounts cannot be changed.
2. **Given** a balance, **When** staff record a payment not exceeding it, **Then** the balance
   and status update, and a confirmation names the new balance.
3. **Given** a walk-in sale, **When** staff choose **Associate customer**, pick or create a
   customer, and enter a reason, **Then** the customer is linked and the change is recorded in
   the sale's history.
4. **Given** a draft sale (saved but not completed), **When** it is opened, **Then** staff can
   continue editing its cart and complete it, using the Create Sale layout.
5. **Given** staff without the matching permission, **When** they view a sale, **Then** the
   Record payment and Cancel actions are not offered.

---

### User Story 4 - Cancel a sale (Priority: P2)

Staff with the cancel permission open **Cancel Sale** from a finalized sale. The screen shows:

- the sale summary (number, customer, item count, payment method, date, status and total);
- a required reason;
- a notice that the sale is recorded as cancelled with their name and the date, and that the
  original stays in the history;
- a confirmation box: "I understand this reverses the payment record".

On confirm, the sale is cancelled and its items return to stock. Any money already received is
shown as a refund due.

**Why this priority**: This happens less often than selling, but must be safe and auditable.

**Independent Test**: Cancel a Completed ₱650 sale with a reason.

- The sale shows Cancelled.
- Stock is restored.
- The refund due is ₱650.00.
- The original sale stays in the list as Cancelled.

**Acceptance Scenarios**:

1. **Given** the Cancel Sale screen, **When** the reason is empty or the box is unticked,
   **Then** Confirm Cancellation is disabled.
2. **Given** a confirmed cancellation, **When** it succeeds, **Then** staff return to the sale,
   which shows Cancelled, the reason, who cancelled it, and the refund due. A confirmation
   names the sale.
3. **Given** a draft or an already-cancelled sale, **When** staff try to cancel it, **Then** the
   action is not offered.
4. **Given** staff without the cancel permission, **When** they open the Cancel Sale address
   directly, **Then** they see the access-denied state.

---

### Edge Cases

- **Many products**: the product grid paginates or scrolls within its panel, and search narrows
  it as staff type.
- **Inactive products**: they never appear in the grid. A product deactivated while in a cart
  makes completion fail, naming the product, and the cart is kept.
- **Archived customers**: they can't be linked, and the server says so.
- **Price changes**: if a product's price changes after it was added to the cart, the sale uses
  the server's current price when completed. The confirmation shows the final totals.
- **Totals**: they are computed from string amounts, never floating point, so ₱0.10 + ₱0.20
  shows ₱0.30.
- **Keyboard use**: the whole Create Sale flow (search, Add, quantity, payment, Complete) works
  by keyboard with a logical focus order (constitution: speed of use).
- **Leaving with a cart**: navigating away from a non-empty cart asks for confirmation, so
  nothing is lost by accident.

## Requirements *(mandatory)*

### Functional Requirements

**Sales list**

- **FR-001**: The Sales screen MUST list sales newest first. It MUST offer search by sale number
  or customer name, a status filter and pagination (20 per page), with the columns from the
  reference: ID, Products, Total, Payment Method and Date, plus a status badge.
- **FR-002**: The back office MUST provide each listed sale's product summary and the distinct
  payment methods of its posted receipts, without adding queries per row.

**Creating sales**

- **FR-003**: Create Sale MUST provide:
  - an optional customer, searchable by name or contact number, with inline creation of a new
    customer (name and contact);
  - a searchable grid of active products showing stock and price, with stock-aware Add buttons;
  - a cart with quantity changes and line removal;
  - an optional sale discount;
  - subtotal, discount and total due;
  - a payment method and amount paid;
  - Complete Sale and Save Draft actions.
- **FR-004**: Completing a sale MUST in one step:
  - create the sale;
  - deduct stock;
  - assign the sale number;
  - record the payment if one was entered.

  It is all or nothing, and resubmitting it MUST NOT create a second sale.
- **FR-005**: The date of sale MUST default to today (the store-local business date). It is
  shown read only to staff without the "backdate sales" permission. Staff with the permission
  can pick an earlier date, never a future one, and must then give a reason.
- **FR-005a**: A backdated sale MUST keep its real completion time for audit purposes. Its
  history MUST record the chosen date, the reason, the staff member and the time. Lists and
  details show the date of sale.
- **FR-006**: Totals shown before completion MUST be computed without floating-point arithmetic.
  The server's totals are authoritative and are shown in the confirmation.

**Viewing and collecting**

- **FR-007**: The Sale screen MUST show the number, status, recorded-by and time, customer or
  walk-in notice, lines, subtotal, discount, total, amount paid, outstanding balance, refund due
  (when cancelled) and payments.
- **FR-008**: Staff with the record-payment permission MUST be able to record a payment toward
  the outstanding balance.
- **FR-009**: Staff MUST be able to link, or change, the customer on a finalized sale. A reason is
  required, and the change is recorded in an append-only sale history with the staff member and
  the time. Nothing else about a finalized sale can be changed.
- **FR-010**: Draft sales MUST be editable (cart, customer, discount) and completable from the
  Create Sale layout.

**Cancelling**

- **FR-011**: Cancel Sale MUST:
  - show the sale summary;
  - require a reason and a confirmation tick;
  - be available only for finalized, not-yet-cancelled sales, and only to staff with the cancel
    permission;
  - return the items to stock;
  - show the refund due afterwards.

**Cost visibility**

- **FR-012**: Sale responses MUST NOT include unit cost or gross profit for staff without the
  "view product cost" permission (carried over from 005).

**General**

- **FR-013**: Every money-changing action MUST end with a confirmation naming the sale and the
  result, for example "Sale S20261127-000142 completed — balance ₱0.00".
- **FR-014**: All screens MUST use the shared components, formatters and status badges from 005,
  meet WCAG 2.1 AA, and define loading, empty, error and success states.

### Key Entities

- **Cart (client-side)**: the lines (product, name, unit price, quantity, available stock), the
  sale discount, the customer (or walk-in), the payment method and the amount paid.
- **Sale** (existing): number, status, customer, lines, totals, payments, timestamps, and
  cancellation details. It gains a products summary and payment methods for the list.
- **Sale history entry** (new, append-only): the sale, the action (customer linked or changed,
  or sale backdated), the old and new values, the reason, the staff member and the time.
- **Date of sale** (new on Sale): the store-local business date the sale belongs to. It equals
  the completion date unless the sale was backdated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can complete a two-item cash sale with a linked customer in under 60 seconds.
- **SC-002**: Adding a product to the cart and seeing updated totals feels instant (≤ 100 ms
  perceived).
- **SC-003**: Completing a sale, including stock deduction and payment, responds within 500 ms
  at the 95th percentile (constitution checkout budget).
- **SC-004**: Retried or double-submitted completions never create duplicate sales (0 duplicates
  in tests).
- **SC-005**: Staff without the cost permission see no cost or profit figures on any sales
  screen, and the back office sends none.
- **SC-006**: Design review finds that the Sales list, Create Sale, Sale details and Cancel Sale
  screens match the references, apart from the documented differences.

## Assumptions

- **Cancel inventory handling**: the Cancel Sale reference offers "return to stock" or "deduct
  as damaged". Per 005's decision, that choice is deferred. Cancelling always returns the items
  to stock, and the screen states this.
- **Split payments**: each sale takes one payment method and amount at completion. Further
  payments, possibly by other methods, are recorded from the Sale screen.
- **Refunds**: refunds for cancelled sales are recorded through the existing payments API by
  staff with the refund permission. A refund screen is out of scope; the Sale screen shows the
  refund due.
- **Line discounts**: the back office supports per-line discounts, but the references show only
  a sale-level discount. The UI offers the sale-level discount only.
- **POS**: the sidebar's POS item stays hidden. Create Sale is reached from Sales.

## Dependencies

- Feature 005: design system, shell, shared components, `useToast`, status badges and
  formatters.
- Existing sales services (draft, items, finalize, record payment, cancel) and the customers API
  (search, create).

## Out of Scope

- Editing a finalized sale's items, prices or payments. Wrong sales are cancelled and rung up
  again.
- The stock-handling choice when cancelling.
- Refund and receipt printing screens.
- Pre-order and stringing payments, which belong to their own areas.
