import { apiDelete, apiGet, apiGetPage, apiPatch, apiPost } from './client'
import type { DateOnly, DateTime, ListParams, Money, Paginated } from './common'
import type { PreOrderStatus } from './preorders'
import type { SaleStatus } from './sales'
import type { StringingStatus } from './stringing'

/** specs/001-customer-management/contracts/customers-api.md */
export interface CustomerListItem {
  id: number
  full_name: string
  phone_number: string
  email: string
  is_active: boolean
}

export interface CustomerArchiveEvent {
  action: 'ARCHIVED' | 'REACTIVATED'
  performed_by: number
  performed_by_name: string
  created_at: DateTime
}

export interface CustomerSummary {
  sales_count: number
  stringing_orders_count: number
  preorders_count: number
  total_spent: Money
  outstanding_balance: Money
  open_preorders_count: number
  unfinished_stringing_orders_count: number
}

export interface Customer extends CustomerListItem {
  address: string
  notes: string
  created_at: DateTime
  updated_at: DateTime
  last_archive_event: CustomerArchiveEvent | null
  summary: CustomerSummary
}

/** Create/update responses also report other active customers sharing the phone number. */
export interface CustomerWriteResult extends Customer {
  duplicate_phone_customers: CustomerListItem[]
}

export interface CustomerWrite {
  full_name: string
  phone_number?: string
  email?: string
  address?: string
  notes?: string
}

export interface CustomerListParams extends ListParams {
  status?: 'active' | 'archived' | 'all'
}

export interface CustomerSaleHistoryItem {
  id: number
  sale_number: string
  finalized_at: DateTime | null
  status: SaleStatus
  total_amount: Money
  amount_paid: Money
  balance: Money
}

export interface CustomerStringingHistoryItem {
  id: number
  order_number: string
  racket_description: string
  string_type: string
  tension: string
  status: StringingStatus
  total_amount: Money
  created_at: DateTime
  completed_at: DateTime | null
}

export interface CustomerPreorderHistoryItem {
  id: number
  order_number: string
  product: number
  product_name: string
  product_sku: string
  quantity: number
  total_amount: Money
  expected_arrival_date: DateOnly | null
  status: PreOrderStatus
  amount_paid: Money
  created_at: DateTime
}

export const customerKeys = {
  all: ['customers'] as const,
  list: (params?: CustomerListParams) => [...customerKeys.all, 'list', params ?? {}] as const,
  detail: (id: number) => [...customerKeys.all, 'detail', id] as const,
  sales: (id: number, params?: ListParams) => [...customerKeys.detail(id), 'sales', params ?? {}] as const,
  stringingOrders: (id: number, params?: ListParams) =>
    [...customerKeys.detail(id), 'stringing-orders', params ?? {}] as const,
  preorders: (id: number, params?: ListParams) => [...customerKeys.detail(id), 'preorders', params ?? {}] as const,
  phoneMatches: (phone: string, excludeId?: number) => [...customerKeys.all, 'phone-matches', phone, excludeId] as const,
}

export const customersApi = {
  list: (params?: CustomerListParams): Promise<Paginated<CustomerListItem>> =>
    apiGetPage<CustomerListItem>('/customers/', params),
  get: (id: number): Promise<Customer> => apiGet<Customer>(`/customers/${id}/`),
  create: (body: CustomerWrite): Promise<CustomerWriteResult> => apiPost<CustomerWriteResult>('/customers/', body),
  update: (id: number, body: Partial<CustomerWrite>): Promise<CustomerWriteResult> =>
    apiPatch<CustomerWriteResult>(`/customers/${id}/`, body),
  remove: (id: number): Promise<void> => apiDelete(`/customers/${id}/`),
  archive: (id: number): Promise<Customer> => apiPost<Customer>(`/customers/${id}/archive/`),
  reactivate: (id: number): Promise<Customer> => apiPost<Customer>(`/customers/${id}/reactivate/`),
  phoneMatches: (phone: string, excludeId?: number): Promise<CustomerListItem[]> =>
    apiGet<CustomerListItem[]>('/customers/phone-matches/', { phone, exclude_id: excludeId }),
  sales: (id: number, params?: ListParams): Promise<Paginated<CustomerSaleHistoryItem>> =>
    apiGetPage<CustomerSaleHistoryItem>(`/customers/${id}/sales/`, params),
  stringingOrders: (id: number, params?: ListParams): Promise<Paginated<CustomerStringingHistoryItem>> =>
    apiGetPage<CustomerStringingHistoryItem>(`/customers/${id}/stringing-orders/`, params),
  preorders: (id: number, params?: ListParams): Promise<Paginated<CustomerPreorderHistoryItem>> =>
    apiGetPage<CustomerPreorderHistoryItem>(`/customers/${id}/preorders/`, params),
}
