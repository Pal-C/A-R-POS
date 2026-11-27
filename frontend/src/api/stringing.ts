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

export type StringingStatus = 'RECEIVED' | 'IN_PROGRESS' | 'READY' | 'COMPLETED' | 'CANCELLED'

/** specs/002-stringing-management/contracts/stringing-api.md (list items omit `notes`). */
export interface StringingOrderListItem {
  id: number
  order_number: string
  /** `null` for walk-in orders. */
  customer: CustomerRef | null
  racket_description: string
  string_type: string
  tension: string
  service_price: Money
  discount_amount: Money
  total_amount: Money
  /** Present only with `stringing.view_stringing_financials`. */
  direct_cost?: Money
  /** Present only with `stringing.view_stringing_financials`. */
  profit?: Money
  amount_paid: Money
  balance: Money
  refund_due: Money
  payment_state: PaymentState
  status: StringingStatus
  status_display: string
  created_by: UserRef
  created_at: DateTime
  updated_at: DateTime
  ready_at: DateTime | null
  completed_at: DateTime | null
  paid_in_full_at: DateTime | null
  cancelled_at: DateTime | null
  cancelled_by: UserRef | null
  cancellation_reason: string
}

export interface StringingOrder extends StringingOrderListItem {
  notes: string
}

export interface StringingOrderWrite {
  customer?: number | null
  racket_description: string
  string_type: string
  tension?: string
  notes?: string
  service_price: Money
  discount_amount?: Money
  direct_cost?: Money
}

export interface StringingOrderListParams extends ListParams {
  /** Comma-separated list of statuses. */
  status?: string
  payment_state?: PaymentState
  customer?: number
  received_from?: DateOnly
  received_to?: DateOnly
  ordering?: '-created_at' | 'created_at' | 'status'
}

export interface StringingStatusChange {
  status: Exclude<StringingStatus, 'CANCELLED'>
  expected_status?: StringingStatus
}

export interface StringingRevenueReport {
  date_from: DateOnly
  date_to: DateOnly
  orders_count: number
  gross_service_price: Money
  total_discounts: Money
  net_revenue: Money
  total_direct_cost: Money
  profit: Money
  total_refunds: Money
  net_revenue_after_refunds: Money
  profit_after_refunds: Money
  cancelled_count: number
  unpaid_count: number
  outstanding_balance: Money
}

export type StringingHistoryEvent = OrderHistoryEvent<StringingStatus>

export const stringingKeys = {
  all: ['stringing'] as const,
  list: (params?: StringingOrderListParams) => [...stringingKeys.all, 'list', params ?? {}] as const,
  detail: (id: number) => [...stringingKeys.all, 'detail', id] as const,
  payments: (id: number, params?: ListParams) => [...stringingKeys.detail(id), 'payments', params ?? {}] as const,
  history: (id: number) => [...stringingKeys.detail(id), 'history'] as const,
  revenue: (dateFrom: DateOnly, dateTo: DateOnly) => [...stringingKeys.all, 'revenue', dateFrom, dateTo] as const,
}

export const stringingApi = {
  list: (params?: StringingOrderListParams): Promise<Paginated<StringingOrderListItem>> =>
    apiGetPage<StringingOrderListItem>('/stringing/orders/', params),
  get: (id: number): Promise<StringingOrder> => apiGet<StringingOrder>(`/stringing/orders/${id}/`),
  create: (body: StringingOrderWrite): Promise<StringingOrder> =>
    apiPost<StringingOrder>('/stringing/orders/', body),
  update: (id: number, body: Partial<StringingOrderWrite>): Promise<StringingOrder> =>
    apiPatch<StringingOrder>(`/stringing/orders/${id}/`, body),
  changeStatus: (id: number, body: StringingStatusChange): Promise<StringingOrder> =>
    apiPost<StringingOrder>(`/stringing/orders/${id}/status/`, body),
  cancel: (id: number, body: { reason: string }): Promise<StringingOrder> =>
    apiPost<StringingOrder>(`/stringing/orders/${id}/cancel/`, body),
  payments: (id: number, params?: ListParams): Promise<Paginated<OrderPayment>> =>
    apiGetPage<OrderPayment>(`/stringing/orders/${id}/payments/`, params),
  recordPayment: (id: number, body: OrderPaymentCreate): Promise<{ payment: OrderPayment; order: StringingOrder }> =>
    apiPost(`/stringing/orders/${id}/payments/`, body),
  history: (id: number): Promise<StringingHistoryEvent[]> =>
    apiGet<StringingHistoryEvent[]>(`/stringing/orders/${id}/history/`),
  revenueReport: (dateFrom: DateOnly, dateTo: DateOnly): Promise<StringingRevenueReport> =>
    apiGet<StringingRevenueReport>('/stringing/reports/revenue/', { date_from: dateFrom, date_to: dateTo }),
}
