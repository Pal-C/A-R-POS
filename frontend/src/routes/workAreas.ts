import { Clock, House, Package, PhilippinePeso, Ribbon, Users, type LucideIcon } from 'lucide-react'
import type { ComponentType } from 'react'
import type { Paginated } from '../api/client'
import { customerKeys, customersApi } from '../api/customers'
import { preorderKeys, preordersApi } from '../api/preorders'
import { saleKeys, salesApi } from '../api/sales'
import { stringingApi, stringingKeys } from '../api/stringing'

export interface WorkAreaPageProps {
  area: WorkArea
}

/** A sub-page of an area, e.g. `/inventory/new`. */
export interface WorkAreaChild {
  /** Relative path, e.g. "new" or ":id/edit". */
  path: string
  title: string
  subtitle: string
  permission?: string
  load: () => Promise<ComponentType<WorkAreaPageProps>>
}

/** One addressable section of the app (specs/005-ui-design/data-model.md WorkArea). */
export interface WorkArea {
  path: string
  /** Sidebar text (e.g. "Services"). */
  navLabel: string
  /** Page header title; uses the constitution's terminology (e.g. "Stringing Orders"). */
  title: string
  subtitle: string
  icon: LucideIcon
  /** When set, the area is hidden from the nav and guarded for users without it. */
  permission?: string
  /** Code-split page component. */
  load: () => Promise<ComponentType<WorkAreaPageProps>>
  children?: WorkAreaChild[]
  /** Optional record count shown on placeholder pages. */
  count?: WorkAreaCount
}

export interface WorkAreaCount {
  /** Plural noun, e.g. "pre-orders". */
  noun: string
  queryKey: readonly unknown[]
  fetch: () => Promise<Paginated<unknown>>
}

const productForm = () => import('../features/products/ProductFormPage').then((m) => m.ProductFormPage)

const placeholder = () =>
  import('../pages/placeholders/WorkAreaPlaceholder').then((m) => m.WorkAreaPlaceholder)

/**
 * Single source of truth for routes, page headers and the sidebar, in the order of
 * the Figma references. POS and Analytics are omitted until they exist (spec Q3).
 */
export const workAreas: WorkArea[] = [
  {
    path: '/',
    navLabel: 'Home',
    title: 'Home',
    subtitle: 'Welcome to Ace&Rally POS',
    icon: House,
    load: () => import('../pages/HomePage').then((m) => m.HomePage),
  },
  {
    path: '/sales',
    navLabel: 'Sales',
    title: 'Sales',
    subtitle: 'View, create, edit, and cancel sales',
    icon: PhilippinePeso,
    load: placeholder,
    count: { noun: 'sales', queryKey: saleKeys.list(), fetch: () => salesApi.list() },
  },
  {
    path: '/inventory',
    navLabel: 'Inventory',
    title: 'Products',
    subtitle: 'View stock levels, add, edit and deactivate products',
    icon: Package,
    load: () => import('../features/products/InventoryPage').then((m) => m.InventoryPage),
    children: [
      {
        path: 'new',
        title: 'Add Product',
        subtitle: 'Create a product record with price, cost and stock',
        load: productForm,
      },
      {
        path: ':id/edit',
        title: 'Edit Product',
        subtitle: 'Update product details, price and stock threshold',
        load: productForm,
      },
    ],
  },
  {
    path: '/stringing',
    navLabel: 'Services',
    title: 'Stringing Orders',
    subtitle: 'Track, update and search racket stringing orders',
    icon: Ribbon,
    load: placeholder,
    count: { noun: 'stringing orders', queryKey: stringingKeys.list(), fetch: () => stringingApi.list() },
  },
  {
    path: '/customers',
    navLabel: 'Customers',
    title: 'Customers',
    subtitle: 'Find and manage customer records',
    icon: Users,
    load: placeholder,
    count: { noun: 'customers', queryKey: customerKeys.list(), fetch: () => customersApi.list() },
  },
  {
    path: '/preorders',
    navLabel: 'Pre-Orders',
    title: 'Pre-orders',
    subtitle: 'Track customer pre-orders and deposits',
    icon: Clock,
    load: placeholder,
    count: { noun: 'pre-orders', queryKey: preorderKeys.list(), fetch: () => preordersApi.list() },
  },
]
