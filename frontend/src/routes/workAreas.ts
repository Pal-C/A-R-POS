import type { ComponentType } from 'react'
import { productKeys, productsApi } from '../api/catalog'
import type { Paginated } from '../api/client'
import { customerKeys, customersApi } from '../api/customers'
import { preorderKeys, preordersApi } from '../api/preorders'
import { saleKeys, salesApi } from '../api/sales'
import { stringingApi, stringingKeys } from '../api/stringing'

export interface WorkAreaPageProps {
  area: WorkArea
}

/** One addressable section of the app (data-model.md#workarea-route-table-entry). */
export interface WorkArea {
  path: string
  /** Navigation text; uses the constitution's terminology. */
  label: string
  /** When set, the area is hidden from the nav and guarded for users without it. */
  permission?: string
  /** Code-split page component. */
  load: () => Promise<ComponentType<WorkAreaPageProps>>
  /** Optional record count shown on the placeholder (exercises the shared query states). */
  count?: WorkAreaCount
}

export interface WorkAreaCount {
  /** Plural noun, e.g. "pre-orders". */
  noun: string
  queryKey: readonly unknown[]
  fetch: () => Promise<Paginated<unknown>>
}

const placeholder = () =>
  import('../pages/placeholders/WorkAreaPlaceholder').then((m) => m.WorkAreaPlaceholder)

/** Single source of truth for routes and navigation. Later features swap `load` for real pages. */
export const workAreas: WorkArea[] = [
  { path: '/', label: 'Home', load: () => import('../pages/HomePage').then((m) => m.HomePage) },
  {
    path: '/sales',
    label: 'Sales',
    load: placeholder,
    count: { noun: 'sales', queryKey: saleKeys.list(), fetch: () => salesApi.list() },
  },
  {
    path: '/products',
    label: 'Products',
    load: placeholder,
    count: { noun: 'products', queryKey: productKeys.list(), fetch: () => productsApi.list() },
  },
  { path: '/inventory', label: 'Inventory', load: placeholder },
  {
    path: '/customers',
    label: 'Customers',
    load: placeholder,
    count: { noun: 'customers', queryKey: customerKeys.list(), fetch: () => customersApi.list() },
  },
  {
    path: '/stringing',
    label: 'Stringing Orders',
    load: placeholder,
    count: { noun: 'stringing orders', queryKey: stringingKeys.list(), fetch: () => stringingApi.list() },
  },
  {
    path: '/preorders',
    label: 'Pre-orders',
    load: placeholder,
    count: { noun: 'pre-orders', queryKey: preorderKeys.list(), fetch: () => preordersApi.list() },
  },
]
