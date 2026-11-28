import type { SaleListItem } from '../../api/sales'

/** Heading text: "Sale #S20261127-000142" (as in the references), or "Draft #42". */
export function saleTitle(sale: Pick<SaleListItem, 'id' | 'sale_number'>): string {
  return sale.sale_number ? `Sale #${sale.sale_number}` : `Draft #${sale.id}`
}

/** "S20261127-000142", or "Draft #42" before a number is assigned. */
export function saleLabel(sale: Pick<SaleListItem, 'id' | 'sale_number'>): string {
  return sale.sale_number ?? `Draft #${sale.id}`
}
