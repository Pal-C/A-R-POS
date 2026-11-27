import { apiGet, apiGetPage, apiPatch, apiPost } from './client'
import type {
  CustomerRef,
  DateOnly,
  DateTime,
  ListParams,
  Money,
  OrderHistoryEvent,
  OrderPayment,
  OrderPaymentCreate,
  Paginated,
  PaymentState,
  UserRef,
} from './common'

export type PreOrderStatus = 'PENDING' | 'ORDERED' | 'ARRIVED' | 'FULFILLED' | 'CANCELLED'

export interface ProductRef {
  id: number
  sku: string
  name: string
  is_active: boolean
}

/** specs/003-preorder-management/contracts/preorders-api.md (list items omit `notes`). */
export interface PreOrderListItem {
  id: number
  order_number: string
  customer: CustomerRef
  product: ProductRef
  quantity: number
  agreed_unit_price: Money
  total_amount: Money
  amount_paid: Money
  balance: Money
  refund_due: Money
  payment_state: PaymentState
  expected_arrival_date: DateOnly | null
  is_overdue: boolean
  status: PreOrderStatus
  status_display: string
  created_by: UserRef
  created_at: DateTime
  updated_at: DateTime
  ordered_at: DateTime | null
  arrived_at: DateTime | null
  fulfilled_at: DateTime | null
  fulfilled_by: UserRef | null
  cancelled_at: DateTime | null
  cancelled_by: UserRef | null
  cancellation_reason: string
}

export interface PreOrder extends PreOrderListItem {
  notes: string
}

export interface PreOrderCreate {
  customer: number
  product: number
  quantity: number
  /** Defaults to the product's selling price. */
  agreed_unit_price?: Money
  expected_arrival_date?: DateOnly | null
  notes?: string
}

export type PreOrderUpdate = Partial<Pick<PreOrderCreate, 'quantity' | 'agreed_unit_price' | 'expected_arrival_date' | 'notes'>>

export interface PreOrderListParams extends ListParams {
  /** Comma-separated list of statuses. */
  status?: string
  payment_state?: PaymentState
  customer?: number
  product?: number
  expected_from?: DateOnly
  expected_to?: DateOnly
  overdue?: true
  ordering?: '-created_at' | 'created_at' | 'expected_arrival_date'
}

export interface PreOrderStatusChange {
  status: Exclude<PreOrderStatus, 'FULFILLED' | 'CANCELLED'>
  expected_status?: PreOrderStatus
}

export interface WaitingCount {
  orders: number
  units: number
}

export interface ProductPreorderSummary {
  product: ProductRef
  waiting: Record<'PENDING' | 'ORDERED' | 'ARRIVED', WaitingCount>
  ordered_preorders: PreOrderListItem[]
}

export interface ArrivalCreate {
  received_quantity: number
  preorder_ids?: number[]
}

export interface ArrivalResult {
  marked: PreOrderListItem[]
  units_used: number
  units_left: number
}

export type PreOrderHistoryEvent = OrderHistoryEvent<PreOrderStatus>

export const preorderKeys = {
  all: ['preorders'] as const,
  list: (params?: PreOrderListParams) => [...preorderKeys.all, 'list', params ?? {}] as const,
  detail: (id: number) => [...preorderKeys.all, 'detail', id] as const,
  payments: (id: number, params?: ListParams) => [...preorderKeys.detail(id), 'payments', params ?? {}] as const,
  history: (id: number) => [...preorderKeys.detail(id), 'history'] as const,
  productSummary: (productId: number) => [...preorderKeys.all, 'product-summary', productId] as const,
}

export const preordersApi = {
  list: (params?: PreOrderListParams): Promise<Paginated<PreOrderListItem>> =>
    apiGetPage<PreOrderListItem>('/preorders/', params),
  get: (id: number): Promise<PreOrder> => apiGet<PreOrder>(`/preorders/${id}/`),
  create: (body: PreOrderCreate): Promise<PreOrder> => apiPost<PreOrder>('/preorders/', body),
  update: (id: number, body: PreOrderUpdate): Promise<PreOrder> => apiPatch<PreOrder>(`/preorders/${id}/`, body),
  changeStatus: (id: number, body: PreOrderStatusChange): Promise<PreOrder> =>
    apiPost<PreOrder>(`/preorders/${id}/status/`, body),
  fulfill: (id: number): Promise<PreOrder> => apiPost<PreOrder>(`/preorders/${id}/fulfill/`),
  cancel: (id: number, body: { reason: string }): Promise<PreOrder> =>
    apiPost<PreOrder>(`/preorders/${id}/cancel/`, body),
  payments: (id: number, params?: ListParams): Promise<Paginated<OrderPayment>> =>
    apiGetPage<OrderPayment>(`/preorders/${id}/payments/`, params),
  recordPayment: (id: number, body: OrderPaymentCreate): Promise<{ payment: OrderPayment; preorder: PreOrder }> =>
    apiPost(`/preorders/${id}/payments/`, body),
  history: (id: number): Promise<PreOrderHistoryEvent[]> =>
    apiGet<PreOrderHistoryEvent[]>(`/preorders/${id}/history/`),
  productSummary: (productId: number): Promise<ProductPreorderSummary> =>
    apiGet<ProductPreorderSummary>(`/preorders/products/${productId}/summary/`),
  markArrived: (productId: number, body: ArrivalCreate): Promise<ArrivalResult> =>
    apiPost<ArrivalResult>(`/preorders/products/${productId}/arrivals/`, body),
}
