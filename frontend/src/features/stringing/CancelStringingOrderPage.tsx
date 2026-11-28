import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toApiError, type FieldErrors } from '../../api/errors'
import { stringingApi, stringingKeys, type StringingOrder } from '../../api/stringing'
import { QueryState } from '../../components/QueryState'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmCheck } from '../../components/ui/ConfirmCheck'
import { RadioGroupField, TextAreaField } from '../../components/ui/fields'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useToast } from '../../components/ui/useToast'
import { formatDate, formatMoney } from '../../lib/format'
import { toCents } from '../../lib/money'
import { invalidateAfterStringing, useStringingOrder } from './hooks'
import { customerName, isOpen, stringLabel } from './stringingDisplay'

const MATERIALS = [
  { value: 'no', label: 'No materials used yet (string and add-ons are unopened)' },
  { value: 'yes', label: 'Materials already used (string cut or applied to the racket)' },
]

/** Grey summary: number, "customer | racket | string @ tension | date", status, amount paid. */
function OrderSummary({ order }: { order: StringingOrder }) {
  const meta = [customerName(order), order.racket_description, stringLabel(order), formatDate(order.created_at)]
  return (
    <div className="ar-summary">
      <div>
        <p className="ar-summary__title fw-bold">Order {order.order_number}</p>
        <p className="ar-summary__meta">{meta.join(' | ')}</p>
      </div>
      <div className="d-flex align-items-center gap-3">
        <StatusBadge domain="stringing" value={order.status} />
        <span className="fs-5 fw-bold">Paid {formatMoney(order.amount_paid)}</span>
      </div>
    </div>
  )
}

function CancelForm({ order }: { order: StringingOrder }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [reason, setReason] = useState('')
  const [materials, setMaterials] = useState('no')
  const [confirmed, setConfirmed] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)
  // Back to where staff came from (list or Details); the list when opened directly.
  const back = () => ((window.history.state as { idx?: number } | null)?.idx ? navigate(-1) : navigate('/stringing'))

  const cancel = useMutation({
    mutationFn: () => stringingApi.cancel(order.id, { reason: reason.trim(), materials_used: materials === 'yes' }),
    onSuccess: async (cancelled) => {
      await invalidateAfterStringing(queryClient)
      const refund = toCents(cancelled.refund_due) > 0n ? ` Refund due ${formatMoney(cancelled.refund_due)}.` : ''
      toast.success(`Order ${cancelled.order_number} cancelled.${refund}`)
      navigate(`/stringing?order=${cancelled.id}`)
    },
    onError: async (e) => {
      const apiError = toApiError(e)
      setErrors(apiError.fieldErrors)
      setAlert(apiError.nonFieldErrors.join(' ') || (Object.keys(apiError.fieldErrors).length ? null : apiError.message))
      await queryClient.invalidateQueries({ queryKey: stringingKeys.all })
    },
  })

  if (!isOpen(order.status)) {
    return (
      <Card className="ar-page ar-form-card">
        <OrderSummary order={order} />
        <p className="mt-3">This order can't be cancelled because it is already {order.status_display}.</p>
        <Link to={`/stringing?order=${order.id}`}>Back to the order</Link>
      </Card>
    )
  }

  return (
    <Card className="ar-page ar-form-card">
      <div className="d-grid gap-3">
        <OrderSummary order={order} />
        <TextAreaField
          label="Reason for cancellation"
          name="reason"
          value={reason}
          onChange={setReason}
          placeholder="Describe why this order is being cancelled"
          rows={4}
          error={errors.reason}
          required
        />
        <RadioGroupField label="Materials" name="materials_used" value={materials} onChange={setMaterials} options={MATERIALS} error={errors.materials_used} />
        <Banner>The cancellation, reason, deposit handling and your name are saved to the audit log. The order is never erased.</Banner>
        <ConfirmCheck label="I understand this order will be marked Cancelled" checked={confirmed} onChange={setConfirmed} />
        {alert && (
          <div className="alert alert-danger ar-alert mb-0" role="alert">
            {alert}
          </div>
        )}
        <div className="ar-form-actions mt-0">
          <Button variant="secondary" onClick={back} disabled={cancel.isPending}>
            Back
          </Button>
          <Button variant="danger-confirm" busy={cancel.isPending} disabled={!reason.trim() || !confirmed} onClick={() => cancel.mutate()}>
            Confirm cancellation
          </Button>
        </div>
      </div>
    </Card>
  )
}

/** /stringing/:id/cancel (route requires stringing.cancel_stringingorder). */
export function CancelStringingOrderPage() {
  const order = useStringingOrder(Number(useParams().id))
  return (
    <QueryState isPending={order.isPending} error={order.error}>
      {order.data && <CancelForm order={order.data} />}
    </QueryState>
  )
}
