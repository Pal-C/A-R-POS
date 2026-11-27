import type { Product } from './catalog'
import { apiGet, apiGetPage, apiPost } from './client'
import type { DateOnly, DateTime, ListParams, Paginated } from './common'

export type MovementType =
  | 'SALE'
  | 'RESTOCK'
  | 'CUSTOMER_RETURN'
  | 'DAMAGE'
  | 'ADJUSTMENT_IN'
  | 'ADJUSTMENT_OUT'
  | 'REVERSAL'

/** backend/inventory/serializers.py InventoryMovementSerializer */
export interface InventoryMovement {
  id: number
  product_id: number
  product_name: string
  product_sku: string
  sale_item: number | null
  movement_type: MovementType
  quantity_change: number
  quantity_before: number
  quantity_after: number
  reason: string
  reference_number: string
  reversal_of: number | null
  created_by_id: number
  created_by: string
  movement_date: DateTime
}

export interface MovementListParams extends ListParams {
  product_id?: number
  movement_type?: MovementType
  start_date?: DateOnly
  end_date?: DateOnly
}

export interface RestockCreate {
  product_id: number
  quantity_received: number
  reason?: string
  reference_number?: string
}

export interface StockAdjustmentCreate {
  product_id: number
  /** Positive increases stock, negative decreases; never zero. */
  quantity_change: number
  reason: string
  reference_number?: string
}

export interface MovementReversal {
  reason: string
  reference_number?: string
}

export interface InventorySummary {
  active_product_count: number
  total_units_in_stock: number
  low_stock_count: number
  out_of_stock_count: number
}

export const inventoryKeys = {
  all: ['inventory'] as const,
  movements: (params?: MovementListParams) => [...inventoryKeys.all, 'movements', params ?? {}] as const,
  movement: (id: number) => [...inventoryKeys.all, 'movement', id] as const,
  lowStock: (params?: ListParams) => [...inventoryKeys.all, 'low-stock', params ?? {}] as const,
  outOfStock: (params?: ListParams) => [...inventoryKeys.all, 'out-of-stock', params ?? {}] as const,
  summary: () => [...inventoryKeys.all, 'summary'] as const,
}

export const inventoryApi = {
  movements: (params?: MovementListParams): Promise<Paginated<InventoryMovement>> =>
    apiGetPage<InventoryMovement>('/inventory/movements/', params),
  movement: (id: number): Promise<InventoryMovement> => apiGet<InventoryMovement>(`/inventory/movements/${id}/`),
  restock: (body: RestockCreate): Promise<InventoryMovement> =>
    apiPost<InventoryMovement>('/inventory/restocks/', body),
  adjust: (body: StockAdjustmentCreate): Promise<InventoryMovement> =>
    apiPost<InventoryMovement>('/inventory/adjustments/', body),
  reverse: (id: number, body: MovementReversal): Promise<InventoryMovement> =>
    apiPost<InventoryMovement>(`/inventory/movements/${id}/reverse/`, body),
  lowStock: (params?: ListParams): Promise<Paginated<Product>> => apiGetPage<Product>('/inventory/low-stock/', params),
  outOfStock: (params?: ListParams): Promise<Paginated<Product>> =>
    apiGetPage<Product>('/inventory/out-of-stock/', params),
  summary: (): Promise<InventorySummary> => apiGet<InventorySummary>('/inventory/summary/'),
}
