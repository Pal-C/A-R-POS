# Research: Customer Management

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-11-26

The Technical Context had no open unknowns: the stack is fixed by the constitution and the user
input. This document records the design decisions the spec left open.

---

## R1. Phone number search and normalization

**Decision**: Store a derived `phone_normalized` column (digits only, indexed) next to the
`phone_number` exactly as staff typed it.

- Normalization strips everything except digits. A leading `63` country code becomes `0` when
  either:
  - the result is 12 digits (a complete number), or
  - the original text starts with `+63`, at any length.

  So `+63 917 123 4567`, `0917-123-4567` and `(0917) 1234567` all normalize to `09171234567`,
  and a partial search `+63 917` normalizes to `0917` and still matches. A bare partial `63917`
  (no `+`) is left alone, because it may be a fragment from the middle of a number.
- The column is filled on every save (model `save()`), so admin edits stay consistent.
- A data migration backfills existing rows.
- When the search text contains only phone characters (digits, spaces, `+ - ( )`), it is
  normalized the same way and matched as a substring of `phone_normalized`.
- Any other search text matches `full_name` (case-insensitive substring).

**Rationale**: FR-007 requires matching regardless of formatting. Normalizing once on write keeps
reads simple and indexable, and keeps the original formatting for display.

**Alternatives considered**:

- *Normalize at query time with database functions (`regexp_replace`)*: not indexable, and the
  logic would be duplicated in every query.
- *Rewrite `phone_number` into a single format*: loses what staff entered, and landline formats
  vary.
- *E.164 parsing library (`phonenumbers`)*: a new dependency for a problem that digit stripping
  plus one prefix rule solves for Philippine numbers. Revisit if international customers matter.

## R2. Name search performance

**Decision**: Use a case-insensitive substring match on `full_name` with no trigram index for now.
Keep the existing `customer_name_idx` for ordering.

**Rationale**: SC-002 targets 1 s for 20,000 customers, and the constitution targets 300 ms for list
endpoints. A sequential `ILIKE '%…%'` over 20k short rows takes a few milliseconds on PostgreSQL.
A `pg_trgm` GIN index adds an extension and migration for no measurable gain at this scale.

**Alternatives considered**: a `pg_trgm` GIN index (deferred until the customer count passes about
100k); full-text search (wrong tool for names and fragments).

**Accents**: searching "Peña" finds "Peña" (exact characters). Accent-insensitive search
("pena" → "Peña") is not required by the spec and would need the `unaccent` extension, so it is
out of scope.

## R3. History summary totals: reusing sales payment rules

**Decision**: Define the "net paid" rule once in the sales app and reuse it.

- The rule: posted receipts minus posted refunds; voided payments are ignored.
- New module `backend/sales/selectors.py` provides:
  - `net_paid_expression(prefix="")`: an aggregate expression for that rule, usable in
    `aggregate()` and `annotate()`.
  - `net_paid_subquery(order_field)`: a per-order subquery for annotating sale, stringing order
    and pre-order lists without N+1 queries.
- `Sale.amount_paid` (Python, uses prefetched payments) stays for single-object use.
- A test asserts that the property and the expression agree on the same data.
- Customer summaries (`backend/customers/selectors.py`) aggregate with these expressions:
  - **Total spent** (FR-013): net paid over the customer's sales that are not drafts and not
    cancelled.
  - **Outstanding balance**: sum of totals minus sum of net paid over non-cancelled, non-draft
    records, per type. This is valid because receipts can never exceed a record's total
    (enforced by `record_payment`), so per-record balances are never negative and the sums
    subtract correctly.
  - Stringing totals use `service_price - discount_amount`; pre-order totals use
    `quantity * agreed_unit_price`. Both are written as database expressions that match the
    models' `total_amount` properties.

**Rationale**: matches the user input ("reuse sales payment totals"). A summary costs a fixed
number of queries (about 6) no matter how many transactions the customer has (SC-004).

**Alternatives considered**:

- *Load every record and call `.amount_paid` / `.balance` in Python*: correct, but O(n) rows and
  memory, which fails SC-004 for 500+ transactions.
- *Stored running totals on Customer*: fast, but adds write-path coupling and a reconciliation risk,
  which conflicts with constitution Principle I (history is the source of truth).

## R4. Draft sales in customer history

**Decision**: Leave draft sales out of customer history lists and summary counts. Drafts are
unfinished carts with no stock or payment effect.

Drafts **do** count as history for the deletion check (R6), because a customer on an open draft is
in use.

**Rationale**: the spec's history fields (sale number, amount paid, balance) only mean something
for finalized sales.

## R5. Archive, reactivate and delete audit trail

**Decision**: Add a new append-only model, `CustomerAuditEvent`:

- Fields: `action` (`ARCHIVED` | `REACTIVATED` | `DELETED`), `customer_ref` (plain integer copy of
  the customer id, indexed, **not** a foreign key), `customer_name` (snapshot), `performed_by`
  (FK to User, PROTECT) and `created_at`.
- `Customer.is_active` stays the archive flag.
- Customer details show the latest archive or reactivate event.

**Rationale**: FR-021 needs who and when for all three actions, and deletions must stay auditable
after the customer row is gone.

- A plain integer reference (no FK) lets a customer with archive events still be deleted, with no
  `SET_NULL` exception to the constitution's PROTECT rule.
- A dedicated model is queryable and typed. Django admin's `LogEntry` would work, but its string
  `object_id` and free-text `change_message` make it hard to query, and it would mix domain audit
  with admin activity.

**Alternatives considered**: `archived_at` / `archived_by` columns on Customer (cannot record
reactivations or deletions); Django `LogEntry` (above).

## R6. Safe deletion (FR-019, FR-019a, delete-race edge case)

**Decision**: `delete_customer(customer_id, user)` runs in one transaction:

1. `select_for_update()` locks the customer row.
2. It checks for any sale (any status, including drafts), stringing order or pre-order linked to
   the customer.
3. If any exist, it raises a validation error that offers archiving instead.
4. Otherwise it writes the `DELETED` audit event, then deletes the customer.

Defense in depth: change `Sale.customer` and `StringingOrder.customer` from `SET_NULL` to `PROTECT`.
`PreOrder.customer` is already PROTECT. A delete that somehow skipped the check then fails instead
of silently detaching history.

**Rationale**:

- PostgreSQL takes a `KEY SHARE` lock on the referenced row when another transaction inserts a
  row pointing at it, and that lock conflicts with our `FOR UPDATE`. So either the attach commits
  first and our check sees it, or our delete commits first and the attach fails its foreign key
  check.
- Django's PostgreSQL foreign keys are `DEFERRABLE INITIALLY DEFERRED`, so in that case the failure
  surfaces at the attaching transaction's commit as an `IntegrityError`.
- Either way, no history is lost.
- `SET_NULL` on transactional foreign keys also breaks constitution Principle I ("Transactional
  foreign keys MUST use `on_delete=PROTECT`"), so the change fixes an existing violation.

**Alternatives considered**: relying on the existence check alone (a race could still delete a
customer with history); soft-delete only (rejected by the user's Q1 answer: option B).

## R7. Duplicate phone warning (FR-003: warn, don't block)

**Decision**:

- A lookup endpoint `GET /api/customers/phone-matches/?phone=…&exclude_id=…` returns active
  customers with the same normalized phone. The UI calls it as the phone field is filled in.
- Create and update **always save**, and their responses include `duplicate_phone_customers` (the
  same list), so a client that skipped the lookup can still show the warning afterwards.

**Rationale**: FR-003 says "warn, without blocking". A `409` / "confirm and resubmit" flow would
block.

**Alternatives considered**: a 409 Conflict with an `allow_duplicate_phone` override (a soft
block, against the spec); a unique constraint (shared household phones are explicitly allowed).

## R8. Permissions

**Decision**:

- **View, create, edit, search, history**: any authenticated user (Django REST Framework default
  `IsAuthenticated`).
- **Archive and reactivate**: a new custom permission, `customers.archive_customer`.
- **Delete**: Django's built-in `customers.delete_customer`, which is separate from archiving
  (FR-020).
- Checks happen in the views, matching the pattern used for sales cancellation and refunds.

## R9. Archived customers on new transactions (FR-017)

**Decision**:

- **Sales**: already refused on draft creation and on customer change. Add the same check to
  `finalize_sale` (draft whose customer was archived in the meantime).
- **Stringing orders and pre-orders**: these apps have no create endpoints or services yet; records
  are only created through Django admin. Add a shared guard, `customers.services.ensure_usable`,
  used by the sales services now.
  - Apply it to stringing order and pre-order forms in Django admin by validating `customer` in
    each `ModelAdmin` form, only when the customer is being newly set, so older records with an
    archived customer can still be edited.
  - Record as a dependency that future stringing and pre-order services must call the guard.

**Rationale**: fulfills FR-017 on every path that exists today without inventing new stringing or
pre-order features, which are out of scope.

**Alternatives considered**: `limit_choices_to={"is_active": True}` on the foreign keys (simple,
but it also blocks editing existing orders whose customer was later archived).

## R10. Frontend scope

**Decision**: This feature delivers the backend API only.

- The React app is still the Vite scaffold, with no shared components, routing or API client
  (see constitution follow-up).
- The customer screens (list/search, form, details with history tabs, archive and delete dialogs)
  will be a separate frontend feature built on the [contracts](contracts/customers-api.md) defined
  here.

**Rationale**: building the UI foundation (shared components, formatters, API client) belongs in
its own feature, which will serve every screen, not just customers.

**Impact**:

- Success criteria SC-001, SC-003 and SC-006 (staff timing, first-attempt success) can only be
  verified once that UI exists. SC-002, SC-004, SC-005 and SC-007 are verified by this feature's
  tests.
- Two functional requirements are UI behaviour. This feature delivers their data and APIs, and the
  frontend feature MUST verify the behaviour itself:
  - FR-015's confirmation step. The API performs the action on request; the UI asks first.
  - FR-018's open-items warning. The API returns the counts and balance in `summary`; the UI shows
    them before confirming.
- The spec's **Screen States** table is the acceptance checklist for that frontend feature.
