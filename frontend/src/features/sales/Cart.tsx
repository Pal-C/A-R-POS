import { Minus, Plus, X } from 'lucide-react'
import { formatMoney } from '../../lib/format'
import { isZero, multiplyMoney } from '../../lib/money'
import type { CartLine, CartTotals } from './cartReducer'

export interface CartProps {
  lines: CartLine[]
  totals: CartTotals
  onQuantity: (productId: number, quantity: number) => void
  onRemove: (productId: number) => void
  error?: string[]
}

/** Cart lines with a quantity stepper, plus the subtotal / discount / total panel. */
export function Cart({ lines, totals, onQuantity, onRemove, error }: CartProps) {
  return (
    <section className="ar-cart" aria-labelledby="cart-heading">
      <h2 id="cart-heading" className="ar-cart__title">
        Cart
      </h2>
      {lines.length === 0 ? (
        <p className="ar-cart__empty">Add products to start the sale.</p>
      ) : (
        <ul className="ar-cart__lines">
          {lines.map((line) => (
            <li key={line.productId} className="ar-cart-line">
              <div className="ar-cart-line__info">
                <p className="ar-cart-line__name" title={line.name}>
                  {line.name}
                </p>
                <p className="ar-cart-line__each">
                  {formatMoney(line.unitPrice, { decimals: 0 })} each
                  {!isZero(line.discount) && <> · -{formatMoney(line.discount)} discount</>}
                  {line.available < 1 && <> · no longer sold</>}
                </p>
              </div>
              <div className="ar-cart-line__qty" role="group" aria-label={`Quantity of ${line.name}`}>
                <button type="button" aria-label={`Decrease ${line.name}`} disabled={line.quantity <= 1} onClick={() => onQuantity(line.productId, line.quantity - 1)}>
                  <Minus size={14} aria-hidden="true" />
                </button>
                <span aria-live="polite">×{line.quantity}</span>
                <button type="button" aria-label={`Increase ${line.name}`} disabled={line.quantity >= line.available} onClick={() => onQuantity(line.productId, line.quantity + 1)}>
                  <Plus size={14} aria-hidden="true" />
                </button>
              </div>
              <span className="ar-cart-line__total">{formatMoney(multiplyMoney(line.unitPrice, line.quantity), { decimals: 0 })}</span>
              <button type="button" className="ar-cart-line__remove" aria-label={`Remove ${line.name} from cart`} onClick={() => onRemove(line.productId)}>
                <X size={18} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="invalid-feedback d-block" role="alert">
          {error.join(' ')}
        </p>
      )}
      <dl className="ar-totals" aria-label="Totals">
        <div>
          <dt>Subtotal</dt>
          <dd>{formatMoney(totals.subtotal)}</dd>
        </div>
        <div>
          <dt>Discount</dt>
          <dd>-{formatMoney(totals.discount)}</dd>
        </div>
        <div className="ar-totals__due">
          <dt>Total Due</dt>
          <dd>{formatMoney(totals.total)}</dd>
        </div>
      </dl>
    </section>
  )
}
