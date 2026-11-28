import { isZero } from '../../lib/money'
import { formatMoney } from '../../lib/format'
import type { OrderTotals } from './orderForm'

/** The invoice lines from the Create SO reference: service, discount, add-ons, total. */
export function InvoiceLines({ totals, stringFromStore, hasStencil, hasGrip }: { totals: OrderTotals; stringFromStore: boolean; hasStencil: boolean; hasGrip: boolean }) {
  return (
    <dl className="ar-invoice" aria-label="Invoice">
      <div>
        <dt>Stringing service</dt>
        <dd>{formatMoney(totals.service)}</dd>
      </div>
      {(stringFromStore || !isZero(totals.discount)) && (
        <div>
          <dt>{stringFromStore ? 'Store-string discount' : 'Discount'}</dt>
          <dd>-{formatMoney(totals.discount)}</dd>
        </div>
      )}
      {hasStencil && (
        <div>
          <dt>Stencil</dt>
          <dd>{formatMoney(totals.stencil)}</dd>
        </div>
      )}
      {hasGrip && (
        <div>
          <dt>Grip</dt>
          <dd>{formatMoney(totals.grip)}</dd>
        </div>
      )}
      <div className="ar-invoice__total">
        <dt>Total</dt>
        <dd>{formatMoney(totals.total)}</dd>
      </div>
    </dl>
  )
}
