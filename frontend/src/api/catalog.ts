import { apiGet, apiGetPage, apiPatch, apiPost } from './client'
import type { DateTime, ListParams, Money, Paginated } from './common'

export const PRODUCT_CATEGORIES: { value: ProductCategory; label: string }[] = [
  { value: 'RACKET', label: 'Racket' },
  { value: 'SPORTS_EQUIPMENT', label: 'Sports Equipment' },
  { value: 'ACCESSORIES', label: 'Accessories' },
  { value: 'APPAREL', label: 'Apparel' },
  { value: 'OTHER', label: 'Other' },
]

export type ProductCategory = 'RACKET' | 'SPORTS_EQUIPMENT' | 'ACCESSORIES' | 'APPAREL' | 'OTHER'
export type StockStatus = 'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK'

/** backend/catalog/serializers.py ProductSerializer */
export interface Product {
  id: number
  sku: string
  name: string
  category: ProductCategory
  subcategory: string
  brand: string
  variant_description: string
  model: string
  supplier: string
  description: string
  selling_price: Money
  /** Present only for staff with `catalog.view_product_cost` (research R8). */
  cost_price?: Money
  stock_quantity: number
  low_stock_threshold: number
  is_low_stock: boolean
  is_out_of_stock: boolean
  stock_status: StockStatus
  is_active: boolean
  created_at: DateTime
  updated_at: DateTime
}

export type ProductWrite = Pick<
  Product,
  | 'sku'
  | 'name'
  | 'category'
  | 'subcategory'
  | 'brand'
  | 'model'
  | 'supplier'
  | 'variant_description'
  | 'description'
  | 'selling_price'
  | 'cost_price'
  | 'low_stock_threshold'
  | 'is_active'
>

export interface ProductCreate extends Partial<ProductWrite> {
  sku: string
  name: string
  category: ProductCategory
  selling_price: Money
  /** Starting stock, recorded as a restock in the same transaction. */
  initial_stock?: number
}

/** Editable fields plus stock (needs `catalog.adjust_stock`). */
export type ProductEditable = Partial<ProductWrite> & { stock_quantity?: number }

export interface ProductUpdate {
  changes: ProductEditable
  /** The values the editor loaded, for every key in `changes` (per-field conflict check). */
  expected: ProductEditable
  reason: string
}

export interface EventUser {
  id: number
  username: string
  display_name: string
}

export type ProductEventAction = 'CREATED' | 'UPDATED' | 'DEACTIVATED' | 'REACTIVATED'

export interface ProductEvent {
  id: number
  action: ProductEventAction
  changes: Record<string, unknown>
  reason: string
  performed_by: EventUser
  created_at: DateTime
}

export interface ProductDetail extends Product {
  last_event: Pick<ProductEvent, 'action' | 'performed_by' | 'created_at'> | null
}

export interface ProductStateChangeResult {
  detail: string
  product: Product
}

export interface ProductListParams extends ListParams {
  category?: ProductCategory
  subcategory?: string
  is_active?: boolean
  min_price?: Money
  max_price?: Money
  stock_status?: StockStatus
}

export const productKeys = {
  all: ['products'] as const,
  list: (params?: ProductListParams) => [...productKeys.all, 'list', params ?? {}] as const,
  detail: (id: number) => [...productKeys.all, 'detail', id] as const,
  history: (id: number, params?: ListParams) => [...productKeys.all, 'history', id, params ?? {}] as const,
}

export const productsApi = {
  list: (params?: ProductListParams): Promise<Paginated<Product>> => apiGetPage<Product>('/products/', params),
  get: (id: number): Promise<ProductDetail> => apiGet<ProductDetail>(`/products/${id}/`),
  create: (body: ProductCreate): Promise<Product> => apiPost<Product>('/products/', body),
  update: (id: number, body: ProductUpdate): Promise<ProductDetail> =>
    apiPatch<ProductDetail>(`/products/${id}/`, body),
  deactivate: (id: number, reason: string): Promise<ProductStateChangeResult> =>
    apiPost<ProductStateChangeResult>(`/products/${id}/deactivate/`, { reason }),
  reactivate: (id: number, reason: string): Promise<ProductStateChangeResult> =>
    apiPost<ProductStateChangeResult>(`/products/${id}/reactivate/`, { reason }),
  history: (id: number, params?: ListParams): Promise<Paginated<ProductEvent>> =>
    apiGetPage<ProductEvent>(`/products/${id}/history/`, params),
}
