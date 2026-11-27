import { apiDelete, apiGet, apiGetPage, apiPatch, apiPost } from './client'
import type { DateTime, ListParams, Money, Paginated } from './common'

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
  description: string
  selling_price: Money
  cost_price: Money
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
  | 'variant_description'
  | 'description'
  | 'selling_price'
  | 'cost_price'
  | 'low_stock_threshold'
  | 'is_active'
>

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
}

export const productsApi = {
  list: (params?: ProductListParams): Promise<Paginated<Product>> => apiGetPage<Product>('/products/', params),
  get: (id: number): Promise<Product> => apiGet<Product>(`/products/${id}/`),
  create: (body: ProductWrite): Promise<Product> => apiPost<Product>('/products/', body),
  update: (id: number, body: Partial<ProductWrite>): Promise<Product> => apiPatch<Product>(`/products/${id}/`, body),
  remove: (id: number): Promise<void> => apiDelete(`/products/${id}/`),
}
