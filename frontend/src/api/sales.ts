import { apiDelete, apiGet, apiGetPage, apiPatch, apiPost } from './client'
import type { DateTime, ListParams, Money, Paginated, PaymentMethod, PaymentStatus, PaymentType } from './common'

export type SaleStatus = 'DRAFT' | 'PENDING_PAYMENT' | 'COMPLETED' | 'CANCELLED'

/** backend/sales/serializers.py SaleItemSerializer */
export interface SaleItem {
  id: number
  product: number
  product_name: string
  product_sku: string
  quantity: number
  unit_selling_price: Money
  unit_cost_price: Money
  discount_amount: Money
  line_subtotal: Money
  line_total: Money
  gross_profit: Money
  created_at: DateTime
}

/** backend/sales/serializers.py PaymentSerializer */
export interface Payment {
  id: number
  sale: number | null
  stringing_order: number | null
  preorder: number | null
  amount: Money
  payment_method: PaymentMethod
  payment_type: PaymentType
  status: PaymentStatus
  payment_date: DateTime
  reference_number: string
  notes: string
  received_by: number
  received_by_name: string
  created_at: DateTime
}

/** backend/sales/serializers.py SaleListSerializer */
export interface SaleListItem {
  id: number
  sale_number: string
  customer: number | null
  customer_name: string | null
  created_by: number
  created_by_name: string
  subtotal: Money
  item_discount_total: Money
  discount_amount: Money
  total_amount: Money
  amount_paid: Money
  balance: Money
  refund_due: Money
  status: SaleStatus
  created_at: DateTime
  finalized_at: DateTime | null
  cancelled_at: DateTime | null
}

/** backend/sales/serializers.py SaleDetailSerializer */
export interface Sale extends SaleListItem {
  items: SaleItem[]
  payments: Payment[]
  cancellation_reason: string
  cancelled_by: number | null
  updated_at: DateTime
}

export interface SaleItemCreate {
  product_id: number
  quantity: number
  discount_amount?: Money
}

export interface SaleCreate {
  customer_id?: number | null
  discount_amount?: Money
  items: SaleItemCreate[]
}

export interface SaleUpdate {
  customer_id?: number | null
  discount_amount?: Money
}

export interface SaleItemUpdate {
  quantity?: number
  discount_amount?: Money
}

export interface SaleListParams extends ListParams {
  status?: SaleStatus
  customer_id?: number
}

export interface PaymentCreate {
  /** Exactly one of sale / stringing_order / preorder. */
  sale?: number | null
  stringing_order?: number | null
  preorder?: number | null
  amount: Money
  payment_method: PaymentMethod
  payment_type?: PaymentType
  reference_number?: string
  /** Required for refunds (the refund reason). */
  notes?: string
}

export interface PaymentListParams extends ListParams {
  sale_id?: number
  stringing_order_id?: number
  preorder_id?: number
  payment_type?: PaymentType
}

export const saleKeys = {
  all: ['sales'] as const,
  list: (params?: SaleListParams) => [...saleKeys.all, 'list', params ?? {}] as const,
  detail: (id: number) => [...saleKeys.all, 'detail', id] as const,
  payments: (params?: PaymentListParams) => [...saleKeys.all, 'payments', params ?? {}] as const,
}

export const salesApi = {
  list: (params?: SaleListParams): Promise<Paginated<SaleListItem>> => apiGetPage<SaleListItem>('/sales/', params),
  get: (id: number): Promise<Sale> => apiGet<Sale>(`/sales/${id}/`),
  create: (body: SaleCreate): Promise<Sale> => apiPost<Sale>('/sales/', body),
  update: (id: number, body: SaleUpdate): Promise<Sale> => apiPatch<Sale>(`/sales/${id}/`, body),
  addItem: (id: number, body: SaleItemCreate): Promise<Sale> => apiPost<Sale>(`/sales/${id}/items/`, body),
  getItem: (id: number, itemId: number): Promise<SaleItem> => apiGet<SaleItem>(`/sales/${id}/items/${itemId}/`),
  updateItem: (id: number, itemId: number, body: SaleItemUpdate): Promise<Sale> =>
    apiPatch<Sale>(`/sales/${id}/items/${itemId}/`, body),
  /** Returns the updated sale. */
  removeItem: (id: number, itemId: number): Promise<Sale> => apiDelete<Sale>(`/sales/${id}/items/${itemId}/`),
  finalize: (id: number): Promise<Sale> => apiPost<Sale>(`/sales/${id}/finalize/`),
  cancel: (id: number, body: { reason: string }): Promise<Sale> => apiPost<Sale>(`/sales/${id}/cancel/`, body),
  payments: (params?: PaymentListParams): Promise<Paginated<Payment>> =>
    apiGetPage<Payment>('/sales/payments/', params),
  recordPayment: (body: PaymentCreate): Promise<Payment> => apiPost<Payment>('/sales/payments/', body),
}
