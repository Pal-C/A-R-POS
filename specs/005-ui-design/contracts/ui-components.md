# Contract: Shared UI components (`frontend/src/components/ui/`)

These are the public props that features 006 and 007 build on. Each component:

- forwards `className` and native attributes where that makes sense;
- uses only design tokens, never hardcoded colors;
- has a unit test, including an axe check where it renders interactive markup.

| Component | Props (essentials) | Notes |
|---|---|---|
| `Button` | `variant: 'primary' \| 'secondary' \| 'danger-confirm' \| 'ghost'`, `icon?: LucideIcon`, `busy?: boolean`, `size?: 'md' \| 'sm'` | Labels are uppercase, as in the references. While `busy`, the button is disabled, shows a spinner and sets `aria-busy`. |
| `IconButton` | `icon`, `label` (required, used as `aria-label`), `variant` | The row Edit and Remove actions, and the filter button. |
| `TextField` / `NumberField` / `MoneyField` / `SelectField` / `TextAreaField` | `label`, `name`, `value`, `onChange`, `error?: string[]`, `hint?`, `required?`, `readOnly?` | The label is linked through `htmlFor`. Errors are rendered with `invalid-feedback` and linked by `aria-describedby`. `MoneyField` shows a `₱` prefix and keeps the value as a string. |
| `CheckboxField` | `label`, `checked`, `onChange`, `error?` | A navy checked box. |
| `ConfirmCheck` | `label`, `checked`, `onChange` | The "I understand…" step. Destructive dialogs keep their confirm button disabled until it is ticked. |
| `SearchBox` | `value`, `onChange`, `placeholder`, `debounceMs = 250` | Has a search icon and a clear button. Calls `onChange` after the debounce. |
| `FilterMenu` | `filters: {name, label, options}[]`, `values`, `onChange`, `onClear` | Opened from the outlined FILTER button, with an active-count badge. |
| `StatusChips` | `items: {value, label, count}[]`, `value`, `onChange` | Pill chips. The selected chip is navy. Uses `aria-pressed`. Built for 007. |
| `DataTable<T>` | `columns: {key, header, render, width?, align?}[]`, `rows: T[]`, `rowKey`, `rowActions?`, `isPending`, `error`, `empty: ReactNode` | A light-blue rounded header and white rows with dividers. Uses `QueryState` for loading, error and empty, and `<caption class="visually-hidden">`. |
| `Pagination` | `page`, `pageSize`, `count`, `onPageChange`, `noun` | Shows "Showing X–Y of N {noun}" and circular page buttons. The current page has `aria-current="page"`. |
| `KpiCard` | `label`, `value`, `caption`, `highlight?: boolean`, `isPending?` | `highlight` gives a navy card with a yellow value. |
| `StatusBadge` | `domain`, `value` (or `spec`) | Looks up `statusBadges.ts`. |
| `Modal` | `open`, `title`, `onClose`, `children`, `footer`, `busy?` | A native `<dialog>`. Escape and the backdrop close it, except while `busy`. Focus returns to the opener. |
| `Banner` | `tone: 'info' \| 'warning'`, `children` | A grey panel with a warning triangle and `role="note"`. |
| `Toast` / `useToast()` | `toast.success(msg)`, `toast.error(msg)` | Rendered by `ToastProvider` in `aria-live="polite"`. |
| `Card` / `SectionTitle` | `title?`, `aside?`, `children` | A white bordered card with a navy section title, e.g. "New product". |

## Layout components (`frontend/src/layouts/`)

| Component | Contract |
|---|---|
| `Sidebar` | `areas: WorkArea[]` (already filtered by permission). Shows the logo slot and `NavLink` items. The active item has a sky background and a yellow left bar. Below 992 px it collapses to icons, and the labels become `title` and `aria-label`. |
| `PageHeader` | `title`, `subtitle`, plus the `SyncPill` and `UserBadge`. The title is the page's `<h1>`. |
| `SyncPill` | Reads `useConnectionStatus()`. Shows "Synced" (navy dot) or "Offline" (yellow dot). Has `role="status"`. |
| `UserBadge` | Initials avatar, display name, and role ("Admin" for superusers, otherwise "Staff"). A menu opens the Sign out action. |

## Formatters (`frontend/src/lib/format.ts`)

```ts
formatMoney(value: Money | number, opts?: { decimals?: 0 | 2 }): string   // "₱11,500" / "₱650.00"
formatCount(n: number): string                                           // "1,234"
formatDate(iso: string): string                                          // "11/08/2026" (store TZ)
formatDateTime(iso: string): string                                      // "11/08/2026, 4:32 PM"
parseMoneyInput(raw: string): Money | null                               // "₱1,200.5" -> "1200.50"
initials(displayName: string): string                                    // "Maria Reyes" -> "MR"
```
