# Feature Specification: Customer Management

**Feature Branch**: `001-customer-management`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Customer Management: Users can create customers, view customer list and details, edit customer information, search customers by name or phone number, deactivate customers(? not sure about this, or maybe delete?), view associated sales, view associated stringing orders, view associated pre-orders."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find a customer at the counter (Priority: P1)

A staff member serving a customer at the counter searches by name or phone number, picks the
right person from the results, and opens their details: contact information and notes.

**Why this priority**: Every other customer action starts with finding the customer. It is also
the step that happens while the customer is waiting, so it must be fast.

**Independent Test**: With a set of existing customers loaded, search by a partial name and by a
partial phone number. The right customer appears in the results and their details open.

**Acceptance Scenarios**:

1. **Given** a customer "Ana Reyes" with phone "0917 123 4567", **When** staff search "ana", **Then**
   Ana Reyes appears in the results.
2. **Given** the same customer, **When** staff search "4567" or "09171234567", **Then** Ana Reyes
   appears in the results, regardless of the spaces or dashes in the stored number.
3. **Given** no customer matches the search, **When** the search runs, **Then** staff see a clear
   "no customers found" message with an option to create a new customer.
4. **Given** more customers exist than fit on one page, **When** staff view the customer list,
   **Then** the list is paged and sorted alphabetically by name.
5. **Given** a customer is selected from the results, **When** their details open, **Then** staff
   see full name, phone number, email, address, notes, active/archived status, and when the
   record was created and last updated.

---

### User Story 2 - Register a new customer (Priority: P1)

Staff add a new customer with at least a name, plus optional phone, email, address and notes, so
the customer can be attached to sales, stringing orders and pre-orders.

**Why this priority**: Pre-orders need a customer, and stringing orders and sales usually have
one. Without this, those workflows cannot record who they are for.

**Independent Test**: Create a customer with only a name, and another with all fields. Both appear
in the list and can be found by search.

**Acceptance Scenarios**:

1. **Given** the new-customer form, **When** staff enter only a full name and save, **Then** the
   customer is created as active and staff see a confirmation.
2. **Given** the form, **When** staff leave the name blank or enter an invalid email, **Then** the
   customer is not saved and the problem is shown next to the field.
3. **Given** an active customer already has phone "09171234567", **When** staff enter the same
   number for a new customer, **Then** staff are warned and shown the existing customer, and can
   still choose to save. Two people can share a household phone.

---

### User Story 3 - Update customer information (Priority: P2)

Staff correct or update a customer's name, phone, email, address or notes when details change or
were entered wrongly.

**Why this priority**: Wrong contact details mean failed pickup notifications for stringing
orders and pre-orders. This is needed early, but it builds on Stories 1 and 2.

**Independent Test**: Edit an existing customer's phone and notes. The new values show in the
customer's details and in search results.

**Acceptance Scenarios**:

1. **Given** an existing customer, **When** staff change the phone number and save, **Then** the
   new number shows everywhere the customer appears and is searchable.
2. **Given** an edit that clears the name or sets an invalid email, **When** staff save, **Then**
   the change is rejected with a message next to the field, and the stored record is unchanged.
3. **Given** a customer with past sales, **When** their name is corrected, **Then** those past
   sales show the corrected name. Customer details are not snapshotted on transactions.

---

### User Story 4 - View a customer's history (Priority: P2)

From a customer's details, staff see that customer's sales, stringing orders and pre-orders, each
with its status and amounts. A summary shows what the customer has spent and what they still
owe.

**Why this priority**: Answers common counter questions such as "is my racket ready?", "what do I
still owe?" and "what did I buy last time?" without searching each area separately.

**Independent Test**: For a customer with one sale, one stringing order and one pre-order, open
their details. All three appear with the correct status and amounts, and the summary totals match.

**Acceptance Scenarios**:

1. **Given** a customer with sales, **When** staff open the customer's history, **Then** each sale
   shows its sale number, date, status, total, amount paid and balance, newest first.
2. **Given** a customer with stringing orders, **When** staff view them, **Then** each shows its
   order number, racket, string, tension, status, price and date, newest first.
3. **Given** a customer with pre-orders, **When** staff view them, **Then** each shows its order
   number, product, quantity, agreed total, expected arrival date, status and amount paid, newest
   first.
4. **Given** any customer, **When** staff view the summary, **Then** they see:
   - the number of sales, stringing orders and pre-orders;
   - total spent, meaning net amounts received on non-cancelled sales;
   - the total outstanding balance across unpaid sales, stringing orders and pre-orders.
5. **Given** a customer with no history, **When** staff view it, **Then** each section shows an
   empty state, not an error.
6. **Given** a customer with many past records, **When** staff view a history section, **Then** it
   is paged rather than loading everything at once.

---

### User Story 5 - Archive, reactivate, or delete customers (Priority: P3)

A manager archives a customer who should no longer be used, such as a duplicate entry or someone
who asked not to be contacted, without losing any of their history. An archived customer can be
reactivated. A customer created by mistake, who has no history at all, can instead be permanently
deleted by a manager with delete permission.

**Why this priority**: Keeps the customer list and search results clean. It is not needed for
daily selling.

**Independent Test**: Archive a customer who has a completed sale. They disappear from the default
list and cannot be picked for a new sale, but their sale still shows them as the customer.
Reactivating restores them.

**Acceptance Scenarios**:

1. **Given** an active customer, **When** a manager archives them and confirms, **Then** the
   customer no longer appears in the default list or search results.
2. **Given** an archived customer, **When** staff try to attach them to a new sale, stringing order
   or pre-order, **Then** the system refuses with a message saying the customer is archived.
3. **Given** an archived customer with past sales, stringing orders and pre-orders, **When** staff
   view those records, **Then** the customer is still shown on each one.
4. **Given** the list filter is set to "archived" or "all", **When** staff search, **Then** archived
   customers appear and are clearly marked as archived.
5. **Given** an archived customer, **When** a manager reactivates them, **Then** they appear in
   default lists again and can be used on new transactions.
6. **Given** a staff member without permission to archive, **When** they try to archive or
   reactivate a customer, **Then** the action is refused.
7. **Given** a customer with an open pre-order or an unpaid balance, **When** a manager archives
   them, **Then** the manager is warned about the open items before confirming. The open items
   themselves are unaffected.
8. **Given** a customer with no sales, stringing orders or pre-orders, **When** a manager with
   delete permission deletes them and confirms, **Then** the customer is permanently removed and no
   longer appears in any list, search or filter.
9. **Given** a customer with any sale, stringing order or pre-order, including cancelled ones,
   **When** anyone tries to delete them, **Then** the system refuses, explains that customers with
   history can only be archived, and offers to archive instead.
10. **Given** a staff member without delete permission, **When** they view a customer, **Then** no
    delete option is offered, and any attempt to delete is refused.

---

### Edge Cases

- **Search input**: searches with leading or trailing spaces, different letter case, or phone
  numbers with spaces, dashes or a "+63" prefix still find matches. An empty search shows the
  default list.
- **Name variants**: very long names, names with accents (e.g., "Peña") or punctuation (e.g.,
  "Dela Cruz-Santos") are stored and found correctly.
- **Concurrent edits**: if two staff members edit the same customer at nearly the same time, the
  last save wins and both see the saved result.
- **Archive in progress**: archiving a customer while a draft sale for them is open stops that draft
  from being finalized until another customer is chosen or the customer is reactivated. This
  matches the existing rule that archived customers cannot be used.
- **Walk-in sales**: sales and stringing orders without a customer do not appear in any customer's
  history.
- **Cancelled records**: cancelled sales, stringing orders and pre-orders appear in history with a
  "Cancelled" status. They count toward the record counts but not toward total spent or
  outstanding balance.
- **Refunds**: refunds reduce total spent, because totals are net of refunds.
- **Delete race**: if a sale, stringing order or pre-order is attached to a customer while their
  deletion is being confirmed, the deletion is refused and nothing is removed.
- **Archived with no history**: an archived customer with no history can still be deleted.

## Requirements *(mandatory)*

### Functional Requirements

**Creating and editing**

- **FR-001**: Users MUST be able to create a customer with a required full name and optional
  phone number, email, address and notes. New customers are active.
- **FR-002**: The system MUST reject a blank (or whitespace-only) name and a malformed email, with a
  message tied to the specific field.
- **FR-003**: The system MUST warn, without blocking, when a new or edited phone number matches an
  existing active customer, and show the matching customer.
- **FR-004**: Users MUST be able to edit a customer's full name, phone number, email, address and
  notes, with the same validation as creation.
- **FR-005**: The system MUST record when each customer was created and last updated. These times
  cannot be edited by users.

**Listing and searching**

- **FR-006**: Users MUST be able to view a paged customer list sorted alphabetically by name,
  showing at least name, phone number and active/archived status.
- **FR-007**: Users MUST be able to search customers by partial, case-insensitive name or partial
  phone number. Phone matching ignores spaces, dashes, parentheses and a leading "+63"/"0" prefix
  difference.
- **FR-008**: The customer list and search MUST show only active customers by default, with a
  filter to show archived or all customers.
- **FR-009**: Users MUST be able to open a customer's details, showing every stored field, status,
  and created/updated times.

**History**

- **FR-010**: Users MUST be able to view a customer's sales with sale number, date, status, total,
  amount paid and balance, newest first and paged.
- **FR-011**: Users MUST be able to view a customer's stringing orders with order number, racket
  description, string type, tension, status, price and dates, newest first and paged.
- **FR-012**: Users MUST be able to view a customer's pre-orders with order number, product,
  quantity, agreed total, expected arrival date, status and amount paid, newest first and paged.
- **FR-013**: The system MUST show a customer summary:
  - the count of sales, stringing orders and pre-orders;
  - total spent (net amounts received on non-cancelled sales);
  - total outstanding balance across unpaid, non-cancelled sales, stringing orders and pre-orders.
- **FR-014**: Each history item MUST link to that record's own detail view where one exists.

**Archiving**

- **FR-015**: Users with archive permission MUST be able to archive and reactivate customers.
  Archiving requires an explicit confirmation step.
- **FR-016**: Archiving MUST NOT change or remove any sale, stringing order, pre-order or payment.
  Those records keep showing the customer.
- **FR-017**: The system MUST prevent archived customers from being attached to new sales, stringing
  orders or pre-orders, from being newly selected on draft sales, and from being on a draft sale
  when it is finalized.
- **FR-018**: Before an archive is confirmed, the system MUST warn about any open pre-orders,
  unfinished stringing orders or unpaid balances for the customer.
- **FR-019**: Customers with any sales, stringing orders or pre-orders, in any status including
  cancelled, MUST NOT be permanently deletable. The refusal MUST explain why and offer archiving
  instead.
- **FR-019a**: Users with delete permission MUST be able to permanently delete a customer who has no
  sales, stringing orders or pre-orders, after an explicit confirmation step. The history check
  MUST be made at the moment of deletion, so a record attached during confirmation blocks it.

**Access and audit**

- **FR-020**: Only signed-in staff MUST be able to access customer information. Archiving and
  reactivating MUST require a dedicated permission. Deleting MUST require a separate, dedicated
  delete permission.
- **FR-021**: The system MUST record who archived, reactivated or deleted a customer and when. For
  deletions, the record MUST keep the deleted customer's name so the action can be audited after
  the customer is gone.

### Key Entities

- **Customer**: A person who buys from, or orders services from, the store. Has a full name, phone
  number, email, address, free-text notes, active/archived status, and created/updated times.
  Archival is reversible. Deletion is permanent and allowed only when the customer has no history.
- **Customer History** (derived, not stored): the customer's sales, stringing orders and pre-orders,
  plus the summary totals calculated from their payments.
- **Sale / Stringing Order / Pre-Order** (existing): transactions that optionally (sales, stringing
  orders) or always (pre-orders) reference a customer. They are read-only from this feature's
  point of view.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Staff can find an existing customer by name or phone and open their details in under
  10 seconds from starting the search.
- **SC-002**: Search results appear within 1 second for a store with up to 20,000 customers.
- **SC-003**: Staff can register a new customer with name and phone in under 30 seconds.
- **SC-004**: A customer's details, summary and first page of each history section load within
  2 seconds, even for a customer with 500+ past transactions.
- **SC-005**: Archiving or reactivating a customer changes 0 existing sales, stringing orders,
  pre-orders or payments, verified by comparing those records before and after.
- **SC-007**: 100% of attempts to delete a customer with any history are refused, and every
  successful deletion is traceable to a named staff member and time.
- **SC-006**: In acceptance testing, staff answer "what does this customer still owe?" and "is
  their stringing order ready?" from the customer's page alone, on the first attempt, in at least
  9 out of 10 trials.

## Assumptions

- **Archive rather than delete**: customers with history are archived, never deleted. This keeps
  sales, stringing and pre-order history intact and matches the project's rule that history is
  never removed. Only customers with no history at all can be deleted, by managers with delete
  permission (decided 2026-11-26).
- **Who can do what**: all signed-in staff can create, view, search and edit customers. Archiving and
  reactivating are limited to staff given the dedicated permission, typically managers. Deleting
  needs its own permission, so a store can allow archiving without allowing deletion.
- **No customer-detail snapshots**: transactions show the customer's current name. Customer details
  are not copied onto past transactions.
- **Phone numbers**: Philippine mobile and landline numbers. Numbers are stored as entered and
  compared after normalization. No SMS verification.
- **Shared phones**: duplicate phone numbers are allowed (households, parent and child) and trigger a
  warning only.
- **Merging duplicates is out of scope**: the workaround is to archive one record.
- **Other out-of-scope items**: loyalty points, customer accounts or self-service, marketing
  consent, data export, and attachments.
- **Dependencies**: the existing sales, stringing order, pre-order and payment records provide the
  history and totals. Sales already refuse archived customers, and this feature extends that rule to
  stringing orders and pre-orders.
