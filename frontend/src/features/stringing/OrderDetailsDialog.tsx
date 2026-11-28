import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { toApiError } from '../../api/errors'
import { stringingApi, stringingKeys, type StringingOrder, type StringingStatus } from '../../api/stringing'
import { useAuth } from '../../auth/useAuth'
import { QueryState } from '../../components/QueryState'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { SelectField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useToast } from '../../components/ui/useToast'
import { cx } from '../../lib/cx'
import { formatDate, formatDateTime, formatMoney } from '../../lib/format'
import { isZero, toCents } from '../../lib/money'
import { paymentMethodLabel } from '../../lib/payments'
import { invalidateAfterStringing, useOrderPayments, useStringingOrder } from './hooks'
import { StringingPaymentDialog, type PaymentMode } from './StringingPaymentDialog'
import { addOnsLabel, ALLOWED_MOVES, customerName, isOpen, materialsLabel, STATUS_LABELS, STEPS } from './stringingDisplay'

function Stepper({ status }: { status: StringingStatus }) {
  const current = STEPS.indexOf(status)
  return (
    <ol className="ar-stepper" aria-label="Progress">
      {STEPS.map((step, index) => (
        <li
          key={step}
          className={cx('ar-stepper__step', index <= current && 'ar-stepper__step--done', index === current && 'ar-stepper__step--current')}
          aria-current={index === current ? 'step' : undefined}
        >
          {STATUS_LABELS[step]}
        </li>
      ))}
    </ol>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function Breakdown({ order }: { order: StringingOrder }) {
  const addOns = [order.has_stencil && 'stencil', order.has_grip && 'grip'].filter(Boolean).join(', ')
  return (
    <dl className="ar-breakdown" aria-label="Amounts">
      <div>
        <dt>Stringing service</dt>
        <dd>{formatMoney(order.service_price)}</dd>
      </div>
      {!isZero(order.discount_amount) && (
        <div>
          <dt>{order.string_from_store ? 'Store-string discount' : 'Discount'}</dt>
          <dd>-{formatMoney(order.discount_amount)}</dd>
        </div>
      )}
      {addOns && (
        <div>
          <dt>Add-ons ({addOns})</dt>
          <dd>{formatMoney(order.add_ons_total)}</dd>
        </div>
      )}
      <div>
        <dt>Total</dt>
        <dd>{formatMoney(order.total_amount)}</dd>
      </div>
      <div>
        <dt>Amount paid</dt>
        <dd>-{formatMoney(order.amount_paid)}</dd>
      </div>
      {order.direct_cost !== undefined && (
        <div>
          <dt>Direct cost / profit</dt>
          <dd>
            {formatMoney(order.direct_cost)} / {formatMoney(order.profit)}
          </dd>
        </div>
      )}
      {order.status === 'CANCELLED' ? (
        <div className="ar-breakdown__due">
          <dt>Refund due</dt>
          <dd>{formatMoney(order.refund_due)}</dd>
        </div>
      ) : (
        <div className="ar-breakdown__due">
          <dt>Balance due</dt>
          <dd>{formatMoney(order.balance)}</dd>
        </div>
      )}
    </dl>
  )
}

function Payments({ order }: { order: StringingOrder }) {
  const payments = useOrderPayments(order.id)
  return (
    <section aria-label="Payments">
      <h3 className="ar-details__heading">Payments</h3>
      <QueryState isPending={payments.isPending} error={payments.error}>
        {payments.data && payments.data.results.length === 0 && <p className="mb-0 text-body-secondary">No payments recorded yet.</p>}
        {payments.data && payments.data.results.length > 0 && (
          <ul className="ar-payment-list">
            {payments.data.results.map((p) => (
              <li key={p.id}>
                <span>
                  {formatDateTime(p.payment_date)} · {p.payment_type === 'REFUND' ? 'Refund' : 'Payment'} · {paymentMethodLabel(p.payment_method)}
                  {p.status === 'VOIDED' && ' (voided)'}
                </span>
                <span className="fw-semibold">
                  {p.payment_type === 'REFUND' ? '-' : ''}
                  {formatMoney(p.amount)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  )
}

function OrderDetails({ order, onClose }: { order: StringingOrder; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { hasPermission } = useAuth()
  const [next, setNext] = useState<StringingStatus | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [payment, setPayment] = useState<PaymentMode | null>(null)
  const open = isOpen(order.status)
  const hasBalance = toCents(order.balance) > 0n
  const canPay = open && hasBalance && hasPermission('sales.record_payment')
  const canRefund = order.status === 'CANCELLED' && toCents(order.refund_due) > 0n && hasPermission('sales.process_refund')
  const canCancel = open && hasPermission('stringing.cancel_stringingorder')
  const blockedByBalance = next === 'COMPLETED' && hasBalance

  const save = useMutation({
    mutationFn: (status: Exclude<StringingStatus, 'CANCELLED'>) => stringingApi.changeStatus(order.id, { status, expected_status: order.status }),
    onSuccess: async (updated) => {
      await invalidateAfterStringing(queryClient)
      toast.success(`Order ${updated.order_number} is now ${updated.status_display}.`)
      onClose()
    },
    onError: async (e) => {
      const apiError = toApiError(e)
      setError(apiError.message)
      // Someone else changed the status: show the current one instead of overwriting it.
      if (apiError.fieldErrors.current_status) {
        setNext('')
        await queryClient.invalidateQueries({ queryKey: stringingKeys.all })
      }
    },
  })

  const submit = () => {
    if (!next || blockedByBalance) return
    setError(null)
    save.mutate(next as Exclude<StringingStatus, 'CANCELLED'>)
  }

  return (
    <Modal
      open
      title={`Order ${order.order_number}`}
      onClose={onClose}
      busy={save.isPending}
      footer={
        <>
          {canCancel && (
            <Link to={`/stringing/${order.id}/cancel`} className="btn ar-btn ar-btn--secondary me-auto">
              Cancel order
            </Link>
          )}
          {open && (
            <Link to={`/stringing/${order.id}/edit`} className="btn ar-btn ar-btn--ghost">
              Edit
            </Link>
          )}
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            Close
          </Button>
          {open && (
            <Button busy={save.isPending} disabled={!next || blockedByBalance} onClick={submit}>
              Save status
            </Button>
          )}
        </>
      }
    >
      <div className="ar-details">
        <div className="d-flex flex-wrap align-items-center gap-3">
          <StatusBadge domain="stringing" value={order.status} />
          {order.status !== 'CANCELLED' && <Stepper status={order.status} />}
        </div>

        {order.status === 'CANCELLED' && (
          <Banner>
            Cancelled {formatDateTime(order.cancelled_at)} by {order.cancelled_by?.username ?? '—'}. Reason: {order.cancellation_reason}. {materialsLabel(order.materials_used)}.
          </Banner>
        )}

        <dl className="ar-details__grid">
          <Detail label="Customer">{customerName(order)}</Detail>
          <Detail label="String">
            {order.string_type}
            {order.string_from_store && ' (store-bought)'}
          </Detail>
          <Detail label="Contact #">{order.customer?.phone_number || '—'}</Detail>
          <Detail label="String color">{order.string_color || '—'}</Detail>
          <Detail label="Racket">{order.racket_description}</Detail>
          <Detail label="Tension">{order.tension || '—'}</Detail>
          <Detail label="Order date">{formatDate(order.created_at)}</Detail>
          <Detail label="Add-ons">{addOnsLabel(order)}</Detail>
          {order.notes && <Detail label="Notes">{order.notes}</Detail>}
        </dl>

        <Breakdown order={order} />
        <Payments order={order} />

        {(canPay || canRefund) && (
          <div>
            {canPay && (
              <Button variant="secondary" size="sm" onClick={() => setPayment('receipt')}>
                Record payment
              </Button>
            )}
            {canRefund && (
              <Button variant="secondary" size="sm" onClick={() => setPayment('refund')}>
                Record refund
              </Button>
            )}
          </div>
        )}

        {open && (
          <div>
            <SelectField
              label="Update status"
              name="next_status"
              value={next}
              onChange={(value) => {
                setNext(value as StringingStatus | '')
                setError(null)
              }}
              options={ALLOWED_MOVES[order.status].map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
              placeholder="Choose the next status"
              error={blockedByBalance ? [`A balance of ${formatMoney(order.balance)} must be paid before pickup. Record the payment first.`] : undefined}
            />
          </div>
        )}

        {error && (
          <div className="alert alert-danger ar-alert mb-0" role="alert">
            {error}
          </div>
        )}
      </div>
      {payment && <StringingPaymentDialog order={order} mode={payment} onClose={() => setPayment(null)} />}
    </Modal>
  )
}

/** Details dialog over the list, opened by `?order=<id>` (specs/007 R7). */
export function OrderDetailsDialog({ id, onClose }: { id: number; onClose: () => void }) {
  const order = useStringingOrder(id)
  if (order.data) return <OrderDetails order={order.data} onClose={onClose} />
  return (
    <Modal open title="Order" onClose={onClose}>
      <QueryState isPending={order.isPending} error={order.error}>
        {null}
      </QueryState>
    </Modal>
  )
}
