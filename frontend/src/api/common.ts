/** Types shared by several domain modules. Mirrors backend TextChoices exactly. */
import type { Money } from './client'

export type { Money, Paginated, ListParams } from './client'

/** ISO 8601 datetime string (UTC). */
export type DateTime = string
/** `YYYY-MM-DD` (store-local business date). */
export type DateOnly = string

export type PaymentMethod = 'CASH' | 'GCASH' | 'MAYA' | 'BANK_TRANSFER' | 'CARD' | 'OTHER'
export type PaymentType = 'RECEIPT' | 'REFUND'
export type PaymentStatus = 'POSTED' | 'VOIDED'
/** Derived payment progress on stringing orders and pre-orders. */
export type PaymentState = 'UNPAID' | 'PARTIAL' | 'PAID'

export interface UserRef {
  id: number
  username: string
}

export interface CustomerRef {
  id: number
  full_name: string
  phone_number: string
  is_active: boolean
}

/** Payment as listed under a stringing order or pre-order. */
export interface OrderPayment {
  id: number
  amount: Money
  payment_method: PaymentMethod
  payment_type: PaymentType
  status: PaymentStatus
  payment_date: DateTime
  reference_number: string
  notes: string
  received_by: number
}

/** Body for recording a receipt or refund on a stringing order or pre-order. */
export interface OrderPaymentCreate {
  payment_type: PaymentType
  amount: Money
  payment_method: PaymentMethod
  reference_number?: string
  notes?: string
  /** Required for refunds. */
  reason?: string
}

/** Audit-history entry shared by stringing orders and pre-orders. */
export interface OrderHistoryEvent<Status extends string> {
  type: 'CREATED' | 'UPDATED' | 'STATUS_CHANGED' | 'CANCELLED' | 'PAYMENT'
  at: DateTime
  by: UserRef | null
  from_status?: Status
  to_status?: Status
  reason?: string
  changes?: Record<string, [unknown, unknown]>
  payment_type?: PaymentType
  amount?: Money
  payment_method?: PaymentMethod
  /** Pre-orders: set on STATUS_CHANGED entries caused by a delivery. */
  arrival?: unknown
}
