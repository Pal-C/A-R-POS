import { Plus, SquarePen, X } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import type { PaymentState } from '../../api/common'
import type { StringingOrderListItem, StringingOrderListParams, StringingStatus } from '../../api/stringing'
import { useAuth } from '../../auth/useAuth'
import { Button } from '../../components/ui/Button'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { FilterMenu, type FilterDefinition } from '../../components/ui/FilterMenu'
import { IconButton } from '../../components/ui/IconButton'
import { Pagination } from '../../components/ui/Pagination'
import { SearchBox } from '../../components/ui/SearchBox'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { StatusChips, type StatusChipItem } from '../../components/ui/StatusChips'
import { formatDate, formatMoney } from '../../lib/format'
import { toCents } from '../../lib/money'
import { STRINGING_PAGE_SIZE, useStatusCounts, useStringingOrders } from './hooks'
import { OrderDetailsDialog } from './OrderDetailsDialog'
import { customerName, isOpen, STATUS_LABELS, stringLabel } from './stringingDisplay'

const CHIP_ORDER: ('' | StringingStatus)[] = ['', 'RECEIVED', 'IN_PROGRESS', 'READY', 'COMPLETED', 'CANCELLED']

const FILTERS: FilterDefinition[] = [
  {
    name: 'payment_state',
    label: 'Payment',
    options: [
      { value: 'UNPAID', label: 'Unpaid' },
      { value: 'PARTIAL', label: 'Partially paid' },
      { value: 'PAID', label: 'Paid' },
    ],
  },
  { name: 'received_from', label: 'Received from', type: 'date' },
  { name: 'received_to', label: 'Received to', type: 'date' },
]

/** The Balance column: what's still owed, or for a cancelled order what may be refunded. */
function balanceCell(order: StringingOrderListItem) {
  if (order.status === 'CANCELLED') {
    return toCents(order.refund_due) > 0n ? <span title="Refund due">{formatMoney(order.refund_due)} refund</span> : formatMoney('0.00')
  }
  return formatMoney(order.balance)
}

/** Stringing Orders list (US2): chips, search, filters and the Details dialog, all in the URL. */
export function StringingOrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const canCancel = hasPermission('stringing.cancel_stringingorder')

  const filters = useMemo(
    () => ({
      search: searchParams.get('search') || undefined,
      payment_state: (searchParams.get('payment_state') || undefined) as PaymentState | undefined,
      received_from: searchParams.get('received_from') || undefined,
      received_to: searchParams.get('received_to') || undefined,
    }),
    [searchParams],
  )
  const status = (searchParams.get('status') || '') as '' | StringingStatus
  const params: StringingOrderListParams = useMemo(
    () => ({ ...filters, status: status || undefined, page: Number(searchParams.get('page')) || 1 }),
    [filters, status, searchParams],
  )
  const orders = useStringingOrders(params)
  const counts = useStatusCounts(filters)
  const openOrder = Number(searchParams.get('order')) || null
  const hasFilters = Object.values(filters).some(Boolean) || !!status

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes) && !('order' in changes)) next.delete('page')
    setSearchParams(next)
  }
  const clearFilters = () => setSearchParams(new URLSearchParams())

  const chips: StatusChipItem[] = CHIP_ORDER.map((value) => ({
    value,
    label: value ? STATUS_LABELS[value] : 'All',
    count: counts.data ? counts.data[value || 'all'] : undefined,
  }))

  const columns: Column<StringingOrderListItem>[] = [
    {
      key: 'id',
      header: 'Order ID',
      className: 'text-nowrap',
      render: (o) => (
        <button type="button" className="btn btn-link p-0 fw-semibold text-decoration-none" onClick={() => update({ order: String(o.id) })}>
          {o.order_number}
        </button>
      ),
    },
    { key: 'customer', header: 'Customer', render: (o) => customerName(o) },
    { key: 'racket', header: 'Racket', width: '18%', render: (o) => <span className="ar-truncate" title={o.racket_description}>{o.racket_description}</span> },
    {
      key: 'string',
      header: 'String / Tension',
      width: '22%',
      render: (o) => {
        const label = stringLabel(o)
        return (
          <span className="ar-truncate" title={label}>
            {label}
          </span>
        )
      },
    },
    { key: 'date', header: 'Date', render: (o) => formatDate(o.created_at) },
    { key: 'status', header: 'Status', render: (o) => <StatusBadge domain="stringing" value={o.status} /> },
    { key: 'balance', header: 'Balance', className: 'text-nowrap', render: balanceCell },
  ]

  return (
    <div className="ar-page">
      <div className="ar-toolbar">
        <SearchBox value={filters.search ?? ''} onChange={(search) => update({ search })} placeholder="Search by order ID, customer, racket or string" />
        <FilterMenu
          filters={FILTERS}
          values={{ payment_state: filters.payment_state ?? '', received_from: filters.received_from ?? '', received_to: filters.received_to ?? '' }}
          onChange={(name, value) => update({ [name]: value })}
          onClear={() => update({ payment_state: undefined, received_from: undefined, received_to: undefined })}
        />
        <span className="ar-toolbar__spacer" />
        <Button icon={Plus} onClick={() => navigate('/stringing/new')}>
          New order
        </Button>
      </div>
      <div className="mb-3">
        <StatusChips items={chips} value={status} onChange={(value) => update({ status: value })} />
      </div>
      <DataTable
        caption="Stringing orders"
        columns={columns}
        rows={orders.data?.results}
        rowKey={(o) => o.id}
        rowActions={(o) => (
          <>
            <IconButton icon={SquarePen} label={`Open order ${o.order_number}`} onClick={() => update({ order: String(o.id) })} />
            {canCancel && isOpen(o.status) && <IconButton icon={X} label={`Cancel order ${o.order_number}`} onClick={() => navigate(`/stringing/${o.id}/cancel`)} />}
          </>
        )}
        isPending={orders.isPending}
        error={orders.error}
        empty={
          hasFilters ? (
            <>
              <p className="mb-0">No stringing orders match your search or filters.</p>
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            </>
          ) : (
            <>
              <p className="mb-0">No stringing orders yet.</p>
              <Button icon={Plus} onClick={() => navigate('/stringing/new')}>
                New order
              </Button>
            </>
          )
        }
      />
      {orders.data && orders.data.count > 0 && (
        <Pagination page={params.page ?? 1} pageSize={STRINGING_PAGE_SIZE} count={orders.data.count} noun="orders" onPageChange={(page) => update({ page: String(page) })} />
      )}
      {openOrder && <OrderDetailsDialog key={openOrder} id={openOrder} onClose={() => update({ order: undefined })} />}
    </div>
  )
}
