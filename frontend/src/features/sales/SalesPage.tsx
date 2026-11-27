import { Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import type { SaleListItem, SaleListParams, SaleStatus } from '../../api/sales'
import { Button } from '../../components/ui/Button'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { FilterMenu, type FilterDefinition } from '../../components/ui/FilterMenu'
import { Pagination } from '../../components/ui/Pagination'
import { SearchBox } from '../../components/ui/SearchBox'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatDateOnly, formatMoney } from '../../lib/format'
import { SALES_PAGE_SIZE, useSales } from './hooks'
import { paymentMethodLabel, saleLabel } from './salesDisplay'

const FILTERS: FilterDefinition[] = [
  {
    name: 'status',
    label: 'Status',
    options: [
      { value: 'DRAFT', label: 'Draft' },
      { value: 'PENDING_PAYMENT', label: 'Pending Payment' },
      { value: 'COMPLETED', label: 'Completed' },
      { value: 'CANCELLED', label: 'Cancelled' },
    ],
  },
]

/** Sales list (US2). Search and filters live in the URL. */
export function SalesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const params: SaleListParams = useMemo(
    () => ({
      page: Number(searchParams.get('page')) || 1,
      search: searchParams.get('search') || undefined,
      status: (searchParams.get('status') || undefined) as SaleStatus | undefined,
    }),
    [searchParams],
  )
  const sales = useSales(params)
  const hasFilters = !!params.search || !!params.status

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next)
  }

  const columns: Column<SaleListItem>[] = [
    {
      key: 'id',
      header: 'ID',
      className: 'text-nowrap',
      render: (s) => (
        <Link to={`/sales/${s.id}`} className="fw-semibold">
          {saleLabel(s)}
        </Link>
      ),
    },
    {
      key: 'products',
      header: 'Products',
      width: '34%',
      render: (s) => (
        <span className="ar-truncate" title={s.items_summary}>
          {s.items_summary || '—'}
        </span>
      ),
    },
    { key: 'customer', header: 'Customer', render: (s) => s.customer_name ?? 'Walk-in' },
    { key: 'total', header: 'Total', render: (s) => formatMoney(s.total_amount) },
    { key: 'method', header: 'Payment Method', render: (s) => s.payment_methods.map(paymentMethodLabel).join(', ') || '—' },
    { key: 'date', header: 'Date', render: (s) => (s.sale_date ? formatDateOnly(s.sale_date) : '—') },
    { key: 'status', header: 'Status', render: (s) => <StatusBadge domain="sale" value={s.status} /> },
  ]

  return (
    <div className="ar-page">
      <div className="ar-toolbar">
        <SearchBox value={params.search ?? ''} onChange={(search) => update({ search })} placeholder="Search by sale number or customer" />
        <FilterMenu filters={FILTERS} values={{ status: params.status ?? '' }} onChange={(name, value) => update({ [name]: value })} onClear={() => setSearchParams(new URLSearchParams())} />
        <span className="ar-toolbar__spacer" />
        <Button icon={Plus} onClick={() => navigate('/sales/new')}>
          Create sale
        </Button>
      </div>
      <DataTable
        caption="Sales"
        columns={columns}
        rows={sales.data?.results}
        rowKey={(s) => s.id}
        isPending={sales.isPending}
        error={sales.error}
        empty={
          hasFilters ? (
            <>
              <p className="mb-0">No sales match your search or filters.</p>
              <Button variant="secondary" onClick={() => setSearchParams(new URLSearchParams())}>
                Clear filters
              </Button>
            </>
          ) : (
            <>
              <p className="mb-0">No sales yet.</p>
              <Button icon={Plus} onClick={() => navigate('/sales/new')}>
                Create sale
              </Button>
            </>
          )
        }
      />
      {sales.data && sales.data.count > 0 && (
        <Pagination page={params.page ?? 1} pageSize={SALES_PAGE_SIZE} count={sales.data.count} noun="sales" onPageChange={(page) => update({ page: String(page) })} />
      )}
    </div>
  )
}
