# Contract: Frontend module interfaces

This is the public surface that later feature screens are built on. Names are binding;
internals are not.

## `src/config.ts`

```ts
export const config: { apiBaseUrl: string } // from import.meta.env.VITE_API_BASE_URL ?? '/api'
```

## `src/api/client.ts`

```ts
export type Money = string;
export interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }
export type ListParams = { page?: number; search?: string; ordering?: string } & Record<string, string | number | boolean | undefined>;

export function apiGet<T>(url: string, params?: object): Promise<T>;
export function apiGetPage<T>(url: string, params?: ListParams): Promise<Paginated<T>>;
export function apiPost<T>(url: string, body?: unknown): Promise<T>;
export function apiPatch<T>(url: string, body: unknown): Promise<T>;
export function apiDelete(url: string): Promise<void>;

/** Registered once by AuthProvider; invoked (debounced) on any 401 except from auth endpoints. */
export function setUnauthenticatedHandler(fn: (() => void) | null): void;
```

Every rejection is an `ApiError`.

## `src/api/errors.ts`

```ts
export type ApiErrorKind = 'validation' | 'unauthenticated' | 'forbidden' | 'not_found'
  | 'conflict' | 'rate_limited' | 'network' | 'unexpected';
export class ApiError extends Error {
  kind: ApiErrorKind; status: number | null;
  fieldErrors: Record<string, string[]>; nonFieldErrors: string[];
}
export function toApiError(err: unknown): ApiError;   // pure; unit-tested per mapping row
export function isApiError(err: unknown): err is ApiError;
```

## `src/api/auth.ts`

```ts
export interface CurrentUser { id: number; username: string; first_name: string; last_name: string;
  display_name: string; is_superuser: boolean; permissions: string[] }
export const authApi: {
  csrf(): Promise<void>; login(username: string, password: string): Promise<CurrentUser>;
  logout(): Promise<void>; me(): Promise<CurrentUser>;
};
```

## Domain modules: `src/api/{catalog,inventory,sales,customers,stringing,preorders}.ts`

Each module exports its types and an object of endpoint functions, for example:

```ts
export const preordersApi = {
  list(params?: PreOrderListParams): Promise<Paginated<PreOrder>>,
  get(id: number): Promise<PreOrder>,
  create(body: PreOrderCreate): Promise<PreOrder>,
  update(id: number, body: PreOrderUpdate): Promise<PreOrder>,
  changeStatus(id: number, body: { status: PreOrderStatus }): Promise<PreOrder>,
  fulfill(id: number): Promise<PreOrder>,
  cancel(id: number, body: { reason: string }): Promise<PreOrder>,
  payments(id: number): Promise<Payment[]>, recordPayment(id: number, body: PaymentCreate): Promise<Payment>,
  history(id: number): Promise<PreOrderEvent[]>,
  // + product summary / arrivals
};
```

The modules cover every route currently registered under `/api/` (catalog, inventory, sales,
customers, stringing, preorders). Each module also exports a `queryKeys` factory, for example
`preorderKeys.list(params)` and `preorderKeys.detail(id)`, for React Query.

## `src/auth/`

```ts
export function AuthProvider(props: { children: ReactNode }): JSX.Element;
export function useAuth(): {
  status: 'checking' | 'authenticated' | 'anonymous' | 'unreachable';
  user: CurrentUser | null;
  endReason: 'signed_out' | 'expired' | null;
  login(username: string, password: string): Promise<void>;   // throws ApiError
  logout(): Promise<void>;                                   // never throws
  retry(): void;                                             // from 'unreachable'
  hasPermission(perm: string): boolean;
};
export function RequireAuth(): JSX.Element;                     // layout route; redirects to /login?next=
export function RequirePermission(props: { permission?: string; children: ReactNode }): JSX.Element;
export function safeNextPath(raw: string | null): string;       // returns "/" unless raw is an in-app path
```

`safeNextPath` accepts only values that start with a single `/`. It rejects `//`, `/\`,
values with a scheme, and `/login`.

## `src/routes/`

```ts
export const workAreas: WorkArea[];        // single source for nav + routes
export const router: ReturnType<typeof createBrowserRouter>;
```

| Path | Element | Guard |
|---|---|---|
| `/login` | `LoginPage` | redirects to `/` if authenticated |
| `/` and work areas | `AppLayout` > page | `RequireAuth` (+ `RequirePermission` when declared) |
| `*` | `NotFoundPage` | none |
