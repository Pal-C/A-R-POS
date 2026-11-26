<!--
Sync Impact Report
- Version change: 1.0.0 → 2.0.0 (MAJOR: core principles redefined around four focus areas)
- Modified principles:
  - I. Auditable, Append-Only Records → moved to "Domain Integrity & Security Constraints"
  - II. Business Logic Lives in the Service Layer → merged into I. Code Quality
  - III. Integrity Enforced at the Database → merged into I. Code Quality (DB constraints) and
    "Domain Integrity & Security Constraints" (money, migrations)
  - IV. Tested Domain Behavior → expanded into II. Testing Standards
  - V. Secure by Default, Least Privilege → moved to "Domain Integrity & Security Constraints"
- Added principles: III. User Experience Consistency; IV. Performance Requirements
- Added sections: Domain Integrity & Security Constraints (replaces "Technology Stack &
  Constraints", whose stack content is retained there)
- Removed sections: none in substance (all v1.0.0 rules retained, relocated as noted)
- Templates: not modified by this command (they read the constitution at runtime)
- Follow-up TODOs:
  - backend/config/settings.py hardcodes SECRET_KEY and DEBUG=True (violates security
    constraints); fix in a separate change.
  - Backend has no linter/formatter configured yet; Principle I requires one (ruff suggested).
  - Performance budgets in Principle IV are initial targets; revisit once real usage data exists.
  - Frontend is still the Vite scaffold; shared UI components required by Principle III do not
    exist yet.
-->

# Ace&Rally POS Constitution

## Core Principles

### I. Code Quality

Code MUST be readable, consistently structured, and keep business rules in one place.

- **Layering**: domain rules (validation, totals, stock changes, state transitions) MUST live in
  each Django app's `services.py`. Views and serializers MUST stay thin: parse input, call a
  service, serialize output. Cross-app writes MUST go through the owning app's services.
- **Transactions**: any service that writes more than one row, or reads-then-writes shared
  state, MUST run inside `transaction.atomic`. Contended rows (products, stock) MUST be locked
  with `select_for_update()` in primary-key order.
- **Explicit state**: state transitions (e.g., sale DRAFT → FINALIZED / CANCELLED) MUST be
  dedicated service functions that verify the current state first. Enumerations MUST use
  `TextChoices` (backend) and union types or enums (frontend), never free-form strings.
- **Static checks**: backend code MUST pass a configured linter/formatter (ruff or equivalent);
  frontend code MUST pass `tsc -b` with `strict` enabled and `eslint` with no errors. `any`
  in TypeScript requires an inline justification comment.
- **Size and clarity**: functions SHOULD do one thing; a function over ~60 lines or a file over
  ~500 lines MUST be justified in review or split. Public service functions MUST have a
  docstring stating side effects (stock, payments, state).
- **No dead code**: commented-out code, unused imports, and placeholder modules MUST NOT be
  merged.

Rationale: a POS evolves through many small features; consistent layering and automated checks
keep each change local and reviewable.

### II. Testing Standards (NON-NEGOTIABLE)

Every behavior that affects money, stock, or access MUST be proven by an automated test.

- **Service tests**: each service function MUST have tests for the success path and for every
  rejection rule it enforces (invalid quantities, negative or excessive discounts, insufficient
  stock, invalid state transitions, inactive products).
- **API tests**: each endpoint MUST have tests for unauthenticated access, unauthorized roles,
  validation errors, and the success response shape.
- **Model/constraint tests**: every database constraint MUST have a test showing it rejects
  invalid data.
- **Concurrency-sensitive paths** (stock deduction, sale finalization) MUST have at least one
  test demonstrating correct behavior under conflicting operations or locking.
- **Frontend**: components containing logic (cart totals, form validation, payment flow) MUST
  have unit tests; the checkout flow MUST have an end-to-end or integration test once it exists.
- **Regression**: every bug fix MUST include a test that fails without the fix.
- **Organization**: backend tests live in each app's `tests/` package, split by concern
  (`test_services.py`, `test_models.py`, `test_*_api.py`). Tests MUST be deterministic and
  independent of execution order.
- **Gate**: the full backend and frontend test suites MUST pass before merge. Coverage for
  `services.py` modules MUST NOT decrease in a pull request.

Rationale: errors in a POS directly cost money or misstate inventory; tests are the cheapest
safeguard.

### III. User Experience Consistency

Staff MUST be able to use every screen the same way, quickly, under counter-side pressure.

- **Shared components**: UI MUST be built from a shared set of components (buttons, forms,
  tables, modals, alerts, money and date display) based on Bootstrap. One-off styling of a
  pattern that already has a shared component is prohibited.
- **Formatting**: currency, quantities, dates, and times MUST be rendered through shared
  formatters, so the same value looks identical everywhere. Times display in the store's local
  timezone; storage stays UTC.
- **Feedback states**: every data-driven view MUST define loading, empty, error, and success
  states. Actions that change money or stock MUST show a clear confirmation of the result.
- **Errors**: API validation errors MUST be returned in a consistent DRF shape with
  human-readable messages, and the UI MUST display them next to the relevant field or as a
  single alert, never raw JSON or stack traces.
- **Destructive actions**: cancellations, refunds, reversals, and deletions MUST require an
  explicit confirmation step naming what will happen.
- **Speed of use**: primary POS flows (product lookup, add to cart, take payment) MUST be fully
  operable by keyboard (and barcode scanner input), with predictable focus order.
- **Accessibility**: UI MUST meet WCAG 2.1 AA for contrast, labels, and focus visibility.
- **Terminology**: domain terms (Sale, Draft, Finalized, Refund, Restock, Stringing Order,
  Pre-order) MUST be used identically in API fields, UI labels, and documentation.

Rationale: inconsistent screens slow staff down and cause mistakes at the register.

### IV. Performance Requirements

The checkout path MUST stay fast enough that the system is never the bottleneck at the counter.

- **API latency budgets** (p95, single store load, measured against PostgreSQL):
  - Product lookup/search and adding items to a draft sale: ≤ 200 ms
  - Sale finalization including stock deduction and payment: ≤ 500 ms
  - Paginated list endpoints: ≤ 300 ms
  - Reports and exports MAY exceed these but MUST paginate or run asynchronously if > 2 s.
- **Query discipline**: endpoints MUST NOT issue N+1 queries; list and detail views MUST use
  `select_related`/`prefetch_related` where relations are serialized. Query counts for key
  endpoints MUST be asserted in tests (`assertNumQueries` or equivalent).
- **Pagination**: all list endpoints MUST be paginated (project default 20 per page); unbounded
  queries over sales, movements, or customers are prohibited.
- **Indexing**: fields used for frequent filtering or lookup (SKU/barcode, status, dates,
  foreign keys on transactional tables) MUST be indexed.
- **Locking scope**: row locks MUST be held only for the duration of the atomic block that
  needs them; no network calls or slow work inside a locked transaction.
- **Frontend**: initial load of the POS screen MUST become interactive in ≤ 2 s on a typical
  store machine; UI response to scanning or adding an item MUST be ≤ 100 ms perceived. Main
  JS bundle SHOULD stay under 300 KB gzipped; larger additions MUST be justified.
- Features that touch the checkout path MUST state their expected impact on these budgets in
  the plan.

Rationale: slow checkout creates queues and pushes staff toward workarounds that bypass the
system's records.

## Domain Integrity & Security Constraints

These rules carry forward from v1.0.0 and apply to every feature.

- **Append-only history**: stock MUST change only through `InventoryMovement` records.
  Finalized sales, payments, refunds, and movements MUST NOT be edited or deleted; corrections
  are new entries (reversals, refunds, adjustments) referencing the original. Transactional
  foreign keys MUST use `on_delete=PROTECT`. Every transactional record MUST capture the acting
  user and a timestamp.
- **Price snapshots**: sale lines MUST snapshot selling and cost price at the time of sale.
- **Money**: monetary values MUST use `Decimal`/`DecimalField`; floats are prohibited.
- **Database constraints**: invariants expressible as constraints (non-negative stock, balance
  equations, uniqueness) MUST be declared in the database as well as validated in services.
- **Migrations**: schema changes ship as committed Django migrations; applied migrations MUST
  NOT be rewritten.
- **Security**: endpoints require authentication by default; sensitive operations (refunds,
  cancellations, stock adjustments, staff/role management, cost visibility) MUST be gated by
  explicit Django permissions. Secrets and environment settings (`SECRET_KEY`, `DEBUG`, DB
  credentials, allowed hosts, CORS origins) MUST come from environment variables and MUST NOT
  be committed. Customer personal data is visible only to roles that need it.
- **Stack**: Python/Django/DRF with django-filter on PostgreSQL (SQLite is not supported);
  React + TypeScript + Vite + Bootstrap with axios on the frontend. Domain apps: `accounts`,
  `catalog`, `inventory`, `sales`, `customers`, `stringing`, `preorders`. New third-party
  dependencies MUST be justified in the feature plan.

## Development Workflow & Quality Gates

- Features follow the Spec Kit flow: specify → (clarify) → plan → tasks → implement. Each plan
  MUST include a Constitution Check covering all four core principles and the constraints above.
- Specs for user-facing features MUST describe the loading, empty, error, and success states
  (Principle III) and any checkout-path performance impact (Principle IV).
- Work happens on feature branches and reaches `main` via pull requests with scoped,
  descriptive commits (e.g., `feat(inventory): ...`, `test(sales): ...`).
- A pull request is mergeable only when: backend and frontend tests pass; linters, formatters,
  and `tsc -b` pass; required migrations are included; no secrets are committed; and query-count
  tests for touched endpoints pass.
- Reviewers MUST check layering and atomicity (I), test completeness (II), use of shared UI
  components and states (III), and query/locking behavior on hot paths (IV).

## Governance

This constitution supersedes conflicting conventions in the repository. A plan that must
deviate from a principle MUST record the deviation in its Complexity Tracking section with the
reason and the simpler alternative that was rejected.

- **Amendments**: proposed via pull request editing this file, stating the rationale, and
  updating the version and Last Amended date. Amendments require approval from the project
  maintainers.
- **Versioning**: semantic versioning. MAJOR for removing or redefining a principle; MINOR for
  adding a principle or section or materially expanding guidance; PATCH for clarifications and
  wording.
- **Compliance**: every pull request review and every `/speckit-plan` Constitution Check MUST
  confirm compliance. Existing code that violates a principle SHOULD be brought into compliance
  when touched; known violations SHOULD be tracked as follow-up tasks. Performance budgets
  SHOULD be reviewed whenever production measurements become available.

**Version**: 2.0.0 | **Ratified**: 2026-11-26 | **Last Amended**: 2026-11-26
