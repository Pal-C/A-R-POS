import { PackagePlus, Plus, RotateCcw, SquarePen, X } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { PRODUCT_CATEGORIES, type Product, type ProductListParams, type StockStatus } from '../../api/catalog'
import { useAuth } from '../../auth/useAuth'
import { Button } from '../../components/ui/Button'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { FilterMenu, type FilterDefinition } from '../../components/ui/FilterMenu'
import { IconButton } from '../../components/ui/IconButton'
import { KpiCard } from '../../components/ui/KpiCard'
import { Pagination } from '../../components/ui/Pagination'
import { SearchBox } from '../../components/ui/SearchBox'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatCount, formatMoney } from '../../lib/format'
import { PRODUCTS_PAGE_SIZE, useInventorySummary, useProducts } from './hooks'
import { productType } from './productDisplay'

export type ProductDialog =
  | { kind: 'receive'; product?: Product }
  | { kind: 'remove'; product: Product }
  | { kind: 'reactivate'; product: Product }

const FILTERS: FilterDefinition[] = [
  { name: 'category', label: 'Category', options: PRODUCT_CATEGORIES },
  {
    name: 'stock_status',
    label: 'Stock status',
    options: [
      { value: 'IN_STOCK', label: 'In Stock' },
      { value: 'LOW_STOCK', label: 'Low Stock' },
      { value: 'OUT_OF_STOCK', label: 'Out of Stock' },
    ],
  },
  {
    name: 'availability',
    label: 'Availability',
    defaultValue: 'active',
    options: [
      { value: 'active', label: 'Active' },
      { value: 'inactive', label: 'Inactive' },
      { value: 'all', label: 'All products' },
    ],
  },
]
const FILTER_NAMES = FILTERS.map((f) => f.name)

function listParams(searchParams: URLSearchParams): ProductListParams {
  const availability = searchParams.get('availability') || 'active'
  return {
    page: Number(searchParams.get('page')) || 1,
    search: searchParams.get('search') || undefined,
    category: (searchParams.get('category') || undefined) as ProductListParams['category'],
    stock_status: (searchParams.get('stock_status') || undefined) as StockStatus | undefined,
    is_active: availability === 'all' ? undefined : availability === 'active',
  }
}

export interface ProductsPageProps {
  /** Opens a dialog (wired by the Inventory page in US4); omitted actions are hidden. */
  onOpenDialog?: (dialog: ProductDialog) => void
}

export function ProductsPage({ onOpenDialog }: ProductsPageProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const canViewCost = hasPermission('catalog.view_product_cost')
  const params = useMemo(() => listParams(searchParams), [searchParams])
  const products = useProducts(params)
  const summary = useInventorySummary()

  const filterValues = Object.fromEntries(FILTER_NAMES.map((name) => [name, searchParams.get(name) ?? '']))
  const hasFilters = !!params.search || FILTERS.some((f) => filterValues[f.name] && filterValues[f.name] !== (f.defaultValue ?? ''))

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next)
  }
  const clearFilters = () => setSearchParams(new URLSearchParams())

  const columns: Column<Product>[] = [
    { key: 'name', header: 'Product', width: '30%', render: (p) => <span className="ar-truncate" title={p.name}>{p.name}</span> },
    { key: 'type', header: 'Type', render: productType },
    { key: 'brand', header: 'Brand', render: (p) => p.brand || '—' },
    { key: 'price', header: 'Price', render: (p) => formatMoney(p.selling_price, { decimals: 0 }) },
    { key: 'stock', header: 'Stock', render: (p) => formatCount(p.stock_quantity) },
    {
      key: 'status',
      header: 'Status',
      render: (p) =>
        p.is_active ? <StatusBadge domain="stock" value={p.stock_status} /> : <StatusBadge domain="product" value="inactive" />,
    },
  ]

  const summaryValue = (n: number | undefined) => (n === undefined ? '—' : formatCount(n))

  return (
    <div className="ar-page">
      <div className="ar-kpis">
        <KpiCard
          label="Total Products"
          value={summaryValue(summary.data?.active_product_count)}
          caption="Active in catalog"
          isPending={summary.isPending}
        />
        <KpiCard
          label="Low Stock"
          value={summaryValue(summary.data?.low_stock_count)}
          caption="At or below threshold"
          highlight
          isPending={summary.isPending}
        />
        <KpiCard
          label="Out of Stock"
          value={summaryValue(summary.data?.out_of_stock_count)}
          caption="Cannot be sold"
          isPending={summary.isPending}
        />
        {canViewCost && (
          <KpiCard
            label="Inventory Value"
            value={formatMoney(summary.data?.inventory_value, { decimals: 0 })}
            caption="At cost"
            isPending={summary.isPending}
          />
        )}
      </div>

      <div className="ar-toolbar">
        <SearchBox
          value={params.search ?? ''}
          onChange={(search) => update({ search })}
          placeholder="Search by name, type or brand"
        />
        <FilterMenu
          filters={FILTERS}
          values={filterValues}
          onChange={(name, value) => update({ [name]: value })}
          onClear={clearFilters}
        />
        <span className="ar-toolbar__spacer" />
        {onOpenDialog && (
          <Button variant="secondary" icon={PackagePlus} onClick={() => onOpenDialog({ kind: 'receive' })}>
            Receive stock
          </Button>
        )}
        <Button icon={Plus} onClick={() => navigate('/inventory/new')}>
          Add product
        </Button>
      </div>

      <DataTable
        caption="Products"
        columns={columns}
        rows={products.data?.results}
        rowKey={(p) => p.id}
        isPending={products.isPending}
        error={products.error}
        rowActions={(p) => (
          <>
            <IconButton icon={SquarePen} label={`Edit ${p.name}`} onClick={() => navigate(`/inventory/${p.id}/edit`)} />
            {onOpenDialog &&
              (p.is_active ? (
                <IconButton icon={X} label={`Remove ${p.name}`} onClick={() => onOpenDialog({ kind: 'remove', product: p })} />
              ) : (
                <IconButton
                  icon={RotateCcw}
                  label={`Reactivate ${p.name}`}
                  onClick={() => onOpenDialog({ kind: 'reactivate', product: p })}
                />
              ))}
          </>
        )}
        empty={
          hasFilters ? (
            <>
              <p className="mb-0">No products match your search or filters.</p>
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            </>
          ) : (
            <>
              <p className="mb-0">No products yet.</p>
              <Button icon={Plus} onClick={() => navigate('/inventory/new')}>
                Add product
              </Button>
            </>
          )
        }
      />

      {products.data && products.data.count > 0 && (
        <Pagination
          page={params.page ?? 1}
          pageSize={PRODUCTS_PAGE_SIZE}
          count={products.data.count}
          noun="products"
          onPageChange={(page) => update({ page: String(page) })}
        />
      )}
    </div>
  )
}
