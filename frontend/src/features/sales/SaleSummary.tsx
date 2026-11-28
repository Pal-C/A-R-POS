import type { Sale } from '../../api/sales'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatDate, formatDateOnly, formatMoney } from '../../lib/format'
import { paymentMethodLabel } from '../../lib/payments'
import { saleTitle } from './salesDisplay'

/** Grey summary block: "Sale #… — customer | n items | method | date", badge and total. */
export function SaleSummary({ sale }: { sale: Sale }) {
  const itemCount = sale.items.reduce((n, item) => n + item.quantity, 0)
  const meta = [
    sale.customer_name ?? 'Walk-in',
    `${itemCount} ${itemCount === 1 ? 'item' : 'items'}`,
    sale.payment_methods.map(paymentMethodLabel).join(', ') || 'Unpaid',
    sale.sale_date ? formatDateOnly(sale.sale_date) : formatDate(sale.created_at),
  ]
  return (
    <div className="ar-summary">
      <div>
        <p className="ar-summary__title fw-bold">{saleTitle(sale)}</p>
        <p className="ar-summary__meta">{meta.join(' | ')}</p>
      </div>
      <div className="d-flex align-items-center gap-3">
        <StatusBadge domain="sale" value={sale.status} />
        <span className="fs-5 fw-bold">{formatMoney(sale.total_amount)}</span>
      </div>
    </div>
  )
}
