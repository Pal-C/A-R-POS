import { Ban, CreditCard, UserPen, Users } from 'lucide-react'
import { useQueries } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { productKeys, productsApi } from '../../api/catalog'
import type { Sale } from '../../api/sales'
import { useAuth } from '../../auth/useAuth'
import { QueryState } from '../../components/QueryState'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatDate, formatDateOnly, formatDateTime, formatMoney } from '../../lib/format'
import { toCents } from '../../lib/money'
import { AssociateCustomerDialog } from './AssociateCustomerDialog'
import { useSale } from './hooks'
import { RecordPaymentDialog } from './RecordPaymentDialog'
import { SaleEditorPage } from './SaleEditorPage'
import { paymentMethodLabel } from '../../lib/payments'
import { saleTitle } from './salesDisplay'

type Item = Sale['items'][number]
type PaymentRow = Sale['payments'][number]

function eventText(event: Sale['events'][number]): string {
  if (event.action === 'BACKDATED') {
    const [, chosen] = (event.changes.sale_date as [string, string]) ?? []
    return `Backdated to ${chosen ? formatDateOnly(chosen) : 'an earlier date'}`
  }
  return 'Customer changed'
}

function SaleDetails({ sale }: { sale: Sale }) {
  const { hasPermission } = useAuth()
  const [dialog, setDialog] = useState<'payment' | 'customer' | null>(null)
  const finalized = sale.status === 'PENDING_PAYMENT' || sale.status === 'COMPLETED'
  const canCollect = finalized && toCents(sale.balance) > 0n && hasPermission('sales.record_payment')
  const canCancel = finalized && hasPermission('sales.cancel_sale')

  const itemColumns: Column<Item>[] = [
    { key: 'product', header: 'Product', width: '40%', render: (i) => <span className="ar-truncate" title={i.product_name}>{i.product_name}</span> },
    { key: 'qty', header: 'Qty', render: (i) => i.quantity },
    { key: 'price', header: 'Unit price', render: (i) => formatMoney(i.unit_selling_price) },
    { key: 'discount', header: 'Discount', render: (i) => (Number(i.discount_amount) ? `-${formatMoney(i.discount_amount)}` : '—') },
    { key: 'total', header: 'Line total', align: 'end', render: (i) => formatMoney(i.line_total) },
  ]
  const paymentColumns: Column<PaymentRow>[] = [
    { key: 'date', header: 'Date', render: (p) => formatDateTime(p.payment_date) },
    { key: 'type', header: 'Type', render: (p) => (p.payment_type === 'REFUND' ? 'Refund' : 'Payment') },
    { key: 'method', header: 'Method', render: (p) => paymentMethodLabel(p.payment_method) },
    { key: 'by', header: 'Received by', render: (p) => p.received_by_name },
    { key: 'amount', header: 'Amount', align: 'end', render: (p) => formatMoney(p.amount) },
  ]

  return (
    <div className="ar-page d-grid gap-4">
      <Card
        title={
          <span className="d-inline-flex align-items-center gap-3">
            {saleTitle(sale)} <StatusBadge domain="sale" value={sale.status} />
          </span>
        }
        aside={<span>Recorded {formatDateTime(sale.finalized_at ?? sale.created_at)} by {sale.created_by_name}</span>}
      >
        <div className="ar-sale-detail__grid">
          <div>
            <p className="form-label mb-1">Date of Sale</p>
            <p className="fs-5 mb-0">{sale.sale_date ? formatDateOnly(sale.sale_date) : formatDate(sale.created_at)}</p>
          </div>
          <div className="ar-sale-detail__customer">
            {sale.customer ? (
              <div className="ar-customer-chip">
                <Users size={20} aria-hidden="true" />
                <div>
                  <p className="mb-0 small text-body-secondary">Customer</p>
                  <p className="mb-0 fw-semibold">{sale.customer_name}</p>
                </div>
              </div>
            ) : (
              <div className="ar-customer-chip ar-customer-chip--muted">
                <Users size={20} aria-hidden="true" />
                <p className="mb-0">Walk-in sale. No customer is linked.</p>
              </div>
            )}
            {finalized && (
              <Button variant="secondary" size="sm" icon={UserPen} onClick={() => setDialog('customer')}>
                {sale.customer ? 'Change customer' : 'Associate customer'}
              </Button>
            )}
          </div>
        </div>

        <DataTable caption="Items" columns={itemColumns} rows={sale.items} rowKey={(i) => i.id} isPending={false} error={null} empty={null} />

        <div className="ar-sale-detail__bottom">
          <dl className="ar-totals ar-totals--panel" aria-label="Totals">
            <div><dt>Subtotal</dt><dd>{formatMoney(sale.subtotal)}</dd></div>
            <div><dt>Discount</dt><dd>-{formatMoney(sale.discount_amount)}</dd></div>
            <div className="ar-totals__due"><dt>Total Due</dt><dd>{formatMoney(sale.total_amount)}</dd></div>
            <div><dt>Amount Paid</dt><dd>{formatMoney(sale.amount_paid)}</dd></div>
            <div><dt>Outstanding Balance</dt><dd>{formatMoney(sale.balance)}</dd></div>
            {sale.status === 'CANCELLED' && <div><dt>Refund Due</dt><dd>{formatMoney(sale.refund_due)}</dd></div>}
          </dl>
          <div className="ar-sale-detail__actions">
            {canCollect && (
              <Button icon={CreditCard} onClick={() => setDialog('payment')}>
                Record payment
              </Button>
            )}
            {canCancel && (
              <Link to={`/sales/${sale.id}/cancel`} className="btn ar-btn ar-btn--secondary">
                <Ban size={18} aria-hidden="true" />
                <span>Cancel sale</span>
              </Link>
            )}
          </div>
        </div>

        {sale.status === 'CANCELLED' && (
          <Banner>
            Cancelled {formatDateTime(sale.cancelled_at)}. Reason: {sale.cancellation_reason || '—'}
          </Banner>
        )}
      </Card>

      <Card title="Payments">
        <DataTable caption="Payments" columns={paymentColumns} rows={sale.payments} rowKey={(p) => p.id} isPending={false} error={null} empty={<p className="mb-0">No payments recorded yet.</p>} />
      </Card>

      {sale.events.length > 0 && (
        <Card title="History">
          <ul className="ar-history">
            {sale.events.map((event) => (
              <li key={event.id}>
                <p className="mb-0 fw-semibold">{eventText(event)}</p>
                <p className="mb-0 small text-body-secondary">
                  {formatDateTime(event.created_at)} by {event.performed_by.display_name} — {event.reason}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {dialog === 'payment' && <RecordPaymentDialog sale={sale} onClose={() => setDialog(null)} />}
      {dialog === 'customer' && <AssociateCustomerDialog sale={sale} onClose={() => setDialog(null)} />}
    </div>
  )
}

/** Loads current price and stock for a draft's products before reopening it in the editor. */
function DraftEditor({ draft }: { draft: Sale }) {
  const products = useQueries({
    queries: draft.items.map((item) => ({
      queryKey: productKeys.detail(item.product),
      queryFn: () => productsApi.get(item.product),
    })),
  })
  const isPending = products.some((p) => p.isPending)
  const error = products.find((p) => p.error)?.error
  const current = Object.fromEntries(
    products.flatMap((p) => (p.data ? [[p.data.id, { selling_price: p.data.selling_price, stock_quantity: p.data.stock_quantity, is_active: p.data.is_active }]] : [])),
  )
  return (
    <QueryState isPending={isPending} error={error}>
      <SaleEditorPage
        key={draft.id}
        draft={draft}
        draftCustomer={draft.customer ? { id: draft.customer, full_name: draft.customer_name ?? '', phone_number: '' } : null}
        currentProducts={current}
      />
    </QueryState>
  )
}

/** /sales/:id — details for finalized sales; drafts continue in the editor. */
export function SaleDetailPage() {
  const id = Number(useParams().id)
  const sale = useSale(id)
  return (
    <QueryState isPending={sale.isPending} error={sale.error}>
      {sale.data && (sale.data.status === 'DRAFT' ? <DraftEditor draft={sale.data} /> : <SaleDetails sale={sale.data} />)}
    </QueryState>
  )
}
