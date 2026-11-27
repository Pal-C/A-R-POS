import type { Product } from '../../api/catalog'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatCount, formatMoney } from '../../lib/format'
import { productType } from './productDisplay'

/** Grey summary block used at the top of product dialogs. */
export function ProductSummary({ product }: { product: Product }) {
  return (
    <div className="ar-summary">
      <div>
        <p className="ar-summary__title fw-bold">
          {product.name} ({productType(product)})
        </p>
        <p className="ar-summary__meta">
          {[product.brand, formatMoney(product.selling_price, { decimals: 0 }), `Stock: ${formatCount(product.stock_quantity)}`]
            .filter(Boolean)
            .join(' | ')}
        </p>
      </div>
      {product.is_active ? (
        <StatusBadge domain="stock" value={product.stock_status} />
      ) : (
        <StatusBadge domain="product" value="inactive" />
      )}
    </div>
  )
}
