import type { PaymentMethod } from '../../api/common'
import type { SaleListItem } from '../../api/sales'
import { STORE_TIME_ZONE } from '../../lib/format'

export const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'CASH', label: 'Cash' },
  { value: 'GCASH', label: 'GCash' },
  { value: 'MAYA', label: 'Maya' },
  { value: 'BANK_TRANSFER', label: 'Bank Transfer' },
  { value: 'CARD', label: 'Card' },
  { value: 'OTHER', label: 'Other' },
]

export function paymentMethodLabel(method: string): string {
  return PAYMENT_METHODS.find((m) => m.value === method)?.label ?? method
}

/** Today's business date (YYYY-MM-DD) in the store's time zone. */
export function todayInStore(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: STORE_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
}

/** Heading text: "Sale #S20261127-000142" (as in the references), or "Draft #42". */
export function saleTitle(sale: Pick<SaleListItem, 'id' | 'sale_number'>): string {
  return sale.sale_number ? `Sale #${sale.sale_number}` : `Draft #${sale.id}`
}

/** "S20261127-000142", or "Draft #42" before a number is assigned. */
export function saleLabel(sale: Pick<SaleListItem, 'id' | 'sale_number'>): string {
  return sale.sale_number ?? `Draft #${sale.id}`
}
