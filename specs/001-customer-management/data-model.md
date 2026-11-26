# Data Model: Customer Management

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## Customer (existing model, extended)

App: `customers`. Table changes are delivered as migrations.

| Field | Type | Rules |
|---|---|---|
| `id` | integer PK | — |
| `full_name` | text, max 150 | Required. Trimmed. Must not be blank after trimming (FR-002). |
| `phone_number` | text, max 30, optional | Stored as entered (trimmed). Allowed characters: digits, spaces, `+ - ( )`. |
| `phone_normalized` | text, max 30, **new**, indexed, not editable | Digits only, with a leading `63` on 12 digits turned into `0` ([R1](research.md#r1-phone-number-search-and-normalization)). Set on every save; empty when there is no phone. |
| `email` | email, optional | Valid email format when present (FR-002). |
| `address` | text, optional | — |
| `notes` | text, optional | — |
| `is_active` | bool, default `true` | `false` means archived. Changed only through the archive and reactivate services. |
| `created_at` | datetime | Set on creation; read-only (FR-005). |
| `updated_at` | datetime | Set on every save; read-only (FR-005). |

**Indexes**: `customer_name_idx (full_name)` (existing); `customer_phone_idx (phone_number)`
(existing, kept); **new** `customer_phone_norm_idx (phone_normalized)`; **new**
`customer_active_name_idx (is_active, full_name)`, which serves the default list (active
customers, ordered by name).

**Meta permissions (new)**: `archive_customer`, "Can archive and reactivate customers". The
built-in `delete_customer` is used for deletion.

**Data migration**: backfill `phone_normalized` for existing rows.

### State transitions

```text
            archive (archive_customer)
  ACTIVE  ─────────────────────────────▶  ARCHIVED
    ▲  │◀───────────────────────────────    │
    │  │      reactivate (archive_customer)  │
    │  │                                     │
    │  └──── delete (delete_customer) ───┐   │
    │        only if no history          ▼   ▼
    │                                  DELETED (row removed; audit event kept)
  create
```

- **Archive**: allowed only from ACTIVE; archiving an archived customer is a validation error.
  Writes an `ARCHIVED` event.
- **Reactivate**: allowed only from ARCHIVED. Writes a `REACTIVATED` event.
- **Delete**: allowed from either state when the customer has **no** sales (any status, including
  drafts), stringing orders or pre-orders, checked under a row lock
  ([R6](research.md#r6-safe-deletion-fr-019-fr-019a-delete-race-edge-case)). Writes a `DELETED`
  event before removing the row.

## CustomerAuditEvent (new model)

App: `customers`. Append-only: never updated or deleted by the application.

| Field | Type | Rules |
|---|---|---|
| `id` | integer PK | — |
| `action` | text choices: `ARCHIVED`, `REACTIVATED`, `DELETED` | Required. |
| `customer_ref` | positive integer, indexed | The customer's id at the time of the action. **Not** a foreign key, so it survives deletion. |
| `customer_name` | text, max 150 | Snapshot of `full_name` at the time of the action. |
| `performed_by` | FK → `accounts.User`, `PROTECT` | Required. |
| `created_at` | datetime, auto | Read-only. |

**Ordering**: newest first. **Index**: `(customer_ref, -created_at)`.

## Changes to existing models

| Model | Change | Why |
|---|---|---|
| `sales.Sale.customer` | `on_delete` `SET_NULL` → `PROTECT` (still nullable) | Constitution Principle I; protects against deletion ([R6](research.md#r6-safe-deletion-fr-019-fr-019a-delete-race-edge-case)). |
| `stringing.StringingOrder.customer` | `on_delete` `SET_NULL` → `PROTECT` (still nullable) | Same. |
| `preorders.PreOrder.customer` | none (already `PROTECT`) | — |

There are no data changes: only the delete behavior changes.

## Derived: Customer Summary (not stored)

Computed by `customers/selectors.py` with the shared net-paid rule from `sales/selectors.py`
([R3](research.md#r3-history-summary-totals-reusing-sales-payment-rules)).

| Field | Definition |
|---|---|
| `sales_count` | Sales for the customer, excluding drafts (cancelled sales included). |
| `stringing_orders_count` | All stringing orders for the customer. |
| `preorders_count` | All pre-orders for the customer. |
| `total_spent` | Net paid (posted receipts − posted refunds) on the customer's sales that are not drafts and not cancelled. |
| `outstanding_balance` | Σ(total − net paid) over non-draft, non-cancelled sales, stringing orders and pre-orders. |
| `open_preorders_count` | Pre-orders not `FULFILLED` and not `CANCELLED` (archive warning, FR-018). |
| `unfinished_stringing_orders_count` | Stringing orders not `COMPLETED` and not `CANCELLED` (FR-018). |
| `last_archive_event` | The latest `ARCHIVED`/`REACTIVATED` event for the customer: action, by, at. |

Totals per type:

- **Sale**: `total_amount`.
- **Stringing order**: `service_price − discount_amount`.
- **Pre-order**: `quantity × agreed_unit_price`.

## Derived: history rows (not stored)

Each list is newest first and paginated; each row carries the record's id for linking (FR-014).

- **Sale row** (FR-010): `id`, `sale_number`, `finalized_at` (or `created_at`), `status`,
  `total_amount`, `amount_paid`, `balance`. `amount_paid` and `balance` are annotated with
  `net_paid_subquery`, not computed per row.
- **Stringing order row** (FR-011): `id`, `order_number`, `racket_description`, `string_type`,
  `tension`, `status`, `total_amount`, `created_at`, `completed_at`.
- **Pre-order row** (FR-012): `id`, `order_number`, product id/name/SKU, `quantity`,
  `total_amount`, `expected_arrival_date`, `status`, `amount_paid`, `created_at`.

## Validation summary (spec → rule)

| Requirement | Enforced in |
|---|---|
| FR-002 blank name, bad email | Serializer field validation, plus the model (`full_name` non-blank check constraint) |
| FR-003 duplicate phone warns only | Selector `phone_matches()`; no constraint |
| FR-017 archived customers not usable | `customers.services.ensure_usable()`, called by sales services (create, update, finalize) and by the stringing/pre-order admin forms |
| FR-019 / FR-019a delete only without history | `customers.services.delete_customer()` (row lock + existence check) and `PROTECT` foreign keys |
| FR-021 audit | `CustomerAuditEvent` written by the archive, reactivate and delete services |

New database check constraint: `customer_full_name_not_blank`, meaning `full_name` is not empty
after trimming.
