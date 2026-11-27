import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { productKeys, productsApi, type Product } from '../../api/catalog'
import { QueryState } from '../../components/QueryState'
import { Button } from '../../components/ui/Button'
import { Pagination } from '../../components/ui/Pagination'
import { SearchBox } from '../../components/ui/SearchBox'
import { formatCount, formatMoney } from '../../lib/format'
import { productType } from '../products/productDisplay'

export interface ProductPickerProps {
  /** Quantity of each product already in the cart, by product id. */
  inCart: Record<number, number>
  onAdd: (product: Product) => void
}

function ProductCard({ product, inCart, onAdd }: { product: Product; inCart: number; onAdd: () => void }) {
  const remaining = product.stock_quantity - inCart
  const soldOut = product.stock_quantity === 0
  return (
    <li className="ar-product-card">
      <p className="ar-product-card__name" title={product.name}>
        {product.name}
      </p>
      <p className="ar-product-card__type">({productType(product)})</p>
      <p className="ar-product-card__meta">
        <span>Stock: {formatCount(product.stock_quantity)}</span>
        <span>{formatMoney(product.selling_price, { decimals: 0 })}</span>
      </p>
      <Button
        icon={remaining > 0 ? Plus : undefined}
        size="sm"
        className="w-100"
        onClick={onAdd}
        disabled={remaining <= 0}
        aria-label={soldOut ? `${product.name} is out of stock` : `Add ${product.name}`}
      >
        {soldOut ? 'Out of stock' : remaining <= 0 ? 'All in cart' : 'Add'}
      </Button>
    </li>
  )
}

/** Navy panel with product search and a paginated grid of product cards. */
export function ProductPicker({ inCart, onAdd }: ProductPickerProps) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const params = { search: search || undefined, is_active: true, page }
  const products = useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => productsApi.list(params),
    placeholderData: keepPreviousData,
  })

  return (
    <section className="ar-picker" aria-labelledby="products-heading">
      <header className="ar-picker__header">
        <h2 id="products-heading" className="ar-picker__title">
          Products
        </h2>
        <SearchBox
          value={search}
          onChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
          placeholder="Search products"
        />
      </header>
      <QueryState
        isPending={products.isPending}
        error={products.error}
        isEmpty={products.data?.count === 0}
        emptyText={search ? 'No products match your search.' : 'No active products yet.'}
      >
        <ul className="ar-product-grid">
          {products.data?.results.map((product) => (
            <ProductCard key={product.id} product={product} inCart={inCart[product.id] ?? 0} onAdd={() => onAdd(product)} />
          ))}
        </ul>
        {products.data && products.data.count > 20 && (
          <Pagination page={page} pageSize={20} count={products.data.count} noun="products" onPageChange={setPage} />
        )}
      </QueryState>
    </section>
  )
}
