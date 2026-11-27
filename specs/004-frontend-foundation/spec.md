# Feature Specification: Frontend Foundation

**Feature Branch**: `004-frontend-foundation`

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "Create the frontend for this app: initialize React + TypeScript + Vite, set up the routing, set up a reusable API client, configure authentication and session handling, set up global state where necessary. Design will be discussed afterward."

## Clarifications

### Session 2026-11-27

- Q: Should this feature add the missing back-office sign-in, sign-out and current-user
  operations? → A: Yes — add them (plus forgery-protection token issuance and sign-in rate
  limiting) with API tests.
- Q: Idle sign-out behavior on a shared counter machine? → A: Keep a sliding server session
  (~8 hours, renewed on activity); no client-side idle timer; staff sign out manually.

## Overview

This feature lays the foundation every staff-facing screen will be built on: a working web
application shell that staff sign in to, navigate between the shop's work areas (Sales,
Products, Inventory, Customers, Stringing Orders, Pre-orders), and that talks to the existing
back office consistently. Visual design is deliberately out of scope; screens in this feature
are functional placeholders that a later design feature will style and fill in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Staff sign in and out (Priority: P1)

A staff member opens the POS in the browser at the start of a shift. Because they are not
signed in, they are taken to a sign-in screen. They enter their username and password and land
on the home screen, which shows who is signed in. At the end of the shift (or when handing the
counter to a colleague) they sign out and are returned to the sign-in screen.

**Why this priority**: Every back-office operation requires an authenticated staff member.
Nothing else in the frontend is usable without it.

**Independent Test**: With a staff account, open the app, sign in, see your name on the home
screen, sign out, and confirm protected screens are no longer reachable.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor, **When** they open any screen of the app, **Then** they are
   shown the sign-in screen, and after signing in successfully they are taken to the screen they
   originally asked for.
2. **Given** the sign-in screen, **When** the staff member enters a wrong username or password,
   **Then** they see a single, human-readable message ("Invalid username or password") without
   revealing which of the two was wrong, and the password field is cleared.
3. **Given** the sign-in screen, **When** either field is empty and they submit, **Then** the
   form is not sent and the empty field is flagged.
4. **Given** a sign-in in progress, **When** the request is pending, **Then** the submit control
   is disabled and a loading indicator is shown, preventing double submission.
5. **Given** a signed-in staff member, **When** they choose "Sign out", **Then** their session is
   ended on the server, any locally held user data is cleared, and they are shown the sign-in
   screen.
6. **Given** a deactivated staff account, **When** that person tries to sign in, **Then** sign-in
   is refused with the same generic message.

---

### User Story 2 - Session survives reloads and ends safely (Priority: P1)

A staff member who is signed in reloads the page or opens the app in a new tab. They stay signed
in without re-entering credentials. If their session ends on the server (expiry, sign-out in
another tab, administrator deactivation), the next action they take returns them to the sign-in
screen with an explanation, rather than leaving them on a broken screen.

**Why this priority**: Staff work under counter pressure; losing a session silently or being
forced to re-sign in on every reload would make the POS unusable.

**Independent Test**: Sign in, reload the page and confirm you are still signed in; then end the
session from another tab and confirm the next action in the first tab leads to the sign-in screen
with a "Your session has ended" message.

**Acceptance Scenarios**:

1. **Given** a signed-in staff member, **When** they reload the page, **Then** the app confirms
   the session with the server and shows the requested screen without asking for credentials,
   displaying a loading state (not the sign-in screen) while it checks.
2. **Given** a session that has expired or was ended elsewhere, **When** the staff member performs
   any action that contacts the server, **Then** they are taken to the sign-in screen with the
   message "Your session has ended. Please sign in again.", and after signing in are returned to
   the screen they were on.
3. **Given** a signed-in staff member who keeps working, **When** they perform actions over a
   shift, **Then** their session is renewed by activity and lasts at least 8 hours from their last
   action; there is no separate client-side idle timer, and staff sign out manually at handover.

---

### User Story 3 - Navigate between work areas (Priority: P2)

A signed-in staff member uses a persistent navigation to move between the shop's work areas:
Home, Sales, Products, Inventory, Customers, Stringing Orders and Pre-orders. Each area has its
own address that can be bookmarked and shared, and browser back/forward work as expected.
Addresses that do not exist show a "Page not found" screen with a way back home.

**Why this priority**: Navigation is the skeleton later features plug their screens into; it is
needed before any domain screen is built but delivers little value alone.

**Independent Test**: Sign in, visit each work area from the navigation, use browser back and
forward, paste a bookmarked work-area address into a new tab, and open an unknown address.

**Acceptance Scenarios**:

1. **Given** a signed-in staff member, **When** they select a work area in the navigation,
   **Then** that area's screen is shown, the address changes to that area's address, and the
   navigation indicates the current area.
2. **Given** a signed-in staff member, **When** they open a work-area address directly, **Then**
   that area is shown.
3. **Given** any user, **When** they open an address that does not exist, **Then** a "Page not
   found" screen is shown with a link back to Home.
4. **Given** a work area that requires a permission the staff member lacks, **When** they try to
   open it, **Then** they see a "You don't have access to this area" screen instead of the
   area's content, and the area is not shown in their navigation.
5. **Given** a signed-in staff member, **When** they visit the sign-in address, **Then** they are
   sent to Home instead.

---

### User Story 4 - Consistent server communication and error feedback (Priority: P2)

Whenever any screen talks to the back office, staff get consistent behavior: a loading state
while waiting, field-level messages when the server rejects input, a single readable alert for
other failures (server down, network lost, unexpected error), and never raw technical output.

**Why this priority**: Principle III of the constitution requires consistent loading, error and
success states. Building this once now prevents every later screen from inventing its own.

**Independent Test**: From a placeholder screen that loads data, observe the loading state; stop
the back office and retry to see the "Cannot reach the server" alert; submit invalid data to an
endpoint and see the per-field messages mapped from the server's response.

**Acceptance Scenarios**:

1. **Given** the server rejects a request with field validation errors, **When** the response is
   received, **Then** the errors are available to the screen keyed by field, plus any general
   (non-field) message, in human-readable text.
2. **Given** the server cannot be reached, **When** a request fails, **Then** staff see "Cannot
   reach the server. Check the connection and try again." and no technical details.
3. **Given** the server returns an unexpected error, **When** the response is received, **Then**
   staff see a generic "Something went wrong" message; technical details are only available in the
   developer console.
4. **Given** a staff member lacks permission for an action, **When** the server refuses it,
   **Then** staff see "You don't have permission to do that." and their session is not ended.
5. **Given** a list from the server, **When** it is displayed, **Then** the paging information
   (total count, next/previous page) is available to the screen so lists are never loaded
   unbounded.

---

### Edge Cases

- Sign-in submitted twice quickly (double-click or Enter held): only one request is sent.
- Several requests fail at the same time because the session expired: staff are redirected to
  sign-in once, with one message, not once per failed request.
- The originally requested address after sign-in points outside the app or to the sign-in screen
  itself: staff are taken to Home instead (no open redirect).
- Sign-out while the server is unreachable: local user data is still cleared and the sign-in
  screen is shown.
- The server's session check is slow on page load: a loading state is shown; protected content
  is never flashed before the check completes.
- Signing out in one tab: other open tabs show the sign-in screen on their next server action
  (see User Story 2, scenario 2).
- A staff member's permissions change while signed in: the change is reflected after their next
  sign-in or page reload.
- The browser is offline when the app loads: the app shows the "Cannot reach the server" state
  with a retry option rather than the sign-in screen.

## Requirements *(mandatory)*

### Functional Requirements

**Authentication & session**

- **FR-001**: The system MUST let staff sign in with their existing staff username and password
  and MUST end the session on sign-out, both on the server and in the browser.
- **FR-002**: The back office MUST offer sign-in, sign-out and "current staff member" operations
  for the frontend to use, returning the staff member's identity (username, display name) and the
  permissions relevant to the UI. These operations do not exist yet and are delivered by this
  feature, together with an operation that issues the forgery-protection token to the frontend.
- **FR-003**: Sign-in failures MUST return one generic message that does not reveal whether the
  username exists, and inactive accounts MUST be refused.
- **FR-004**: Repeated failed sign-in attempts from the same source MUST be slowed or temporarily
  blocked (rate limited) by the back office.
- **FR-005**: The system MUST keep staff signed in across page reloads and new tabs for the
  lifetime of the server session, without storing passwords or long-lived secrets in browser
  storage readable by page scripts.
- **FR-006**: Every state-changing request from the frontend MUST be protected against
  cross-site request forgery.
- **FR-007**: When any request reports the session is no longer valid, the system MUST clear the
  local signed-in state, show the sign-in screen with a "session ended" message, and return the
  staff member to the screen they were on after signing in again.
- **FR-008**: After sign-in, the system MUST only redirect to addresses inside the app; any other
  target MUST fall back to Home.

**Routing & navigation**

- **FR-009**: The app MUST provide distinct, bookmarkable addresses for: Sign in, Home, Sales,
  Products, Inventory, Customers, Stringing Orders, Pre-orders, and a Not Found screen.
- **FR-010**: All addresses except Sign in and Not Found MUST require a signed-in staff member.
- **FR-011**: A work area MAY declare a required permission; staff without it MUST see an access
  denied screen for that area and MUST NOT see it in the navigation.
- **FR-012**: Each work area in this feature MUST be a placeholder screen stating the area's name;
  real content is delivered by later features.
- **FR-013**: The navigation MUST show the signed-in staff member's display name and a Sign out
  action on every protected screen.

**Server communication**

- **FR-014**: All communication with the back office MUST go through one shared client that
  applies the configured server address, credentials, forgery protection and error handling, so
  screens do not repeat these concerns.
- **FR-015**: The shared client MUST translate server responses into a consistent error form
  distinguishing: validation errors (per field plus general messages), not signed in, not
  permitted, not found, conflict/business-rule rejection, server unreachable, and unexpected error.
- **FR-016**: The shared client MUST provide typed access to the existing back-office areas used
  by upcoming screens (products, inventory, sales, customers, stringing orders, pre-orders) and
  MUST expose paging information for list results.
- **FR-017**: The back-office address MUST be configurable per environment (development,
  production) without code changes.

**Shared application state**

- **FR-018**: The signed-in staff member (identity and permissions) and the session status
  (checking, signed in, signed out) MUST be available to any screen without each screen fetching
  it again.
- **FR-019**: Data fetched from the back office MUST be cached and shared between screens that
  request the same data, with loading, error and success states exposed to the screen, and MUST
  be cleared on sign-out so the next staff member never sees the previous one's data.
- **FR-020**: Only state that is genuinely shared across screens MUST be held globally; screen-
  specific form and view state MUST stay local to the screen.

**Quality**

- **FR-021**: The frontend MUST pass strict type checking and linting with no errors, and the
  authentication flow, route protection and error translation MUST be covered by automated tests.
- **FR-022**: Any back-office additions made by this feature MUST be covered by API tests for
  unauthenticated access, validation errors and the success response shape.

### Key Entities

- **Staff Session**: whether a staff member is signed in; states: checking, signed in, signed
  out; carries the reason it ended (signed out, expired) for messaging.
- **Current Staff Member**: identity of the signed-in user (id, username, display name) and the
  set of permissions the UI uses to show or hide areas and actions.
- **API Error**: a normalized failure with a kind (validation, unauthenticated, forbidden, not
  found, conflict, network, unexpected), a human-readable message, and optional per-field
  messages.
- **Paged List**: a page of results with total count and links to the next and previous pages.
- **Work Area (Route)**: a named, addressable section of the app with an optional required
  permission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A staff member can go from opening the app to the home screen, signed in, in under
  15 seconds.
- **SC-002**: After a page reload, a signed-in staff member sees their requested screen without
  re-entering credentials 100% of the time while the server session is valid.
- **SC-003**: 100% of protected addresses are unreachable without signing in (verified by
  automated tests over every route).
- **SC-004**: When a session ends, the staff member is returned to the sign-in screen on their
  next action, and after signing in lands back on the same screen, in 100% of tested cases.
- **SC-005**: No raw technical error text (stack traces, raw server payloads) is ever shown to
  staff across all tested failure kinds.
- **SC-006**: After sign-out, no data belonging to the previous staff member is visible to the
  next person who signs in on the same machine.
- **SC-007**: The signed-in app shell becomes interactive in 2 seconds or less on a typical store
  machine (constitution Principle IV).

## Assumptions

- Staff accounts already exist (created via the back-office admin); account creation, password
  reset and role management screens are out of scope.
- The back office's existing cookie-based session sign-in will be reused rather than introducing
  a separate token scheme; this keeps credentials out of script-readable browser storage.
- The frontend and back office are served from addresses the back office already allows
  (development: the local frontend dev server); production hosting and deployment are out of
  scope.
- Visual design, layout, branding and the shared UI component library are out of scope and
  covered by a later design feature; screens here use minimal default styling.
- Domain screens (actual product lists, sale flow, customer forms, etc.) are out of scope; only
  their addresses and placeholders are created.
- The existing frontend folder contains only the starter scaffold, which may be replaced.
- Display texts are in English for now.
- Sessions are sliding: renewed on each request and expiring about 8 hours after the last
  activity (roughly one shift). No client-side idle timer.

## Dependencies

- Existing back-office APIs for products, inventory, sales, customers, stringing orders and
  pre-orders (features 001–003 and earlier work).
- Back-office sign-in / sign-out / current-staff-member operations are added by this feature
  (see FR-002).
