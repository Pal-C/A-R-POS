import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toApiError } from '../../api/errors'
import { salesApi, type Sale } from '../../api/sales'
import { useAuth } from '../../auth/useAuth'
import { QueryState } from '../../components/QueryState'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmCheck } from '../../components/ui/ConfirmCheck'
import { TextAreaField } from '../../components/ui/fields'
import { useToast } from '../../components/ui/useToast'
import { formatDateOnly, formatMoney } from '../../lib/format'
import { invalidateAfterSale, useSale } from './hooks'
import { SaleSummary } from './SaleSummary'
import { saleLabel, todayInStore } from './salesDisplay'

function CancelForm({ sale }: { sale: Sale }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { user } = useAuth()
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const back = `/sales/${sale.id}`

  const cancel = useMutation({
    mutationFn: () => salesApi.cancel(sale.id, { reason: reason.trim() }),
    onSuccess: async (cancelled) => {
      await invalidateAfterSale(queryClient)
      toast.success(`Sale ${saleLabel(sale)} cancelled. Refund due ${formatMoney(cancelled.refund_due)}.`)
      navigate(back)
    },
    onError: (e) => setError(toApiError(e).message),
  })

  if (sale.status !== 'PENDING_PAYMENT' && sale.status !== 'COMPLETED') {
    return (
      <Card className="ar-page ar-form-card">
        <SaleSummary sale={sale} />
        <p className="mt-3">This sale can't be cancelled because it is {sale.status === 'DRAFT' ? 'still a draft' : 'already cancelled'}.</p>
        <Link to={back}>Back to the sale</Link>
      </Card>
    )
  }

  return (
    <Card className="ar-page ar-form-card">
      <div className="d-grid gap-3">
        <SaleSummary sale={sale} />
        <TextAreaField label="Reason for cancellation" name="reason" value={reason} onChange={setReason} placeholder="Describe why this sale is being cancelled" rows={4} required />
        <Banner>
          Items are returned to stock. Recorded as cancelled by {user?.display_name} on {formatDateOnly(todayInStore())}. The
          original sale stays in the history and is never erased.
        </Banner>
        <ConfirmCheck label="I understand this reverses the payment record" checked={confirmed} onChange={setConfirmed} />
        {error && (
          <div className="alert alert-danger ar-alert" role="alert">
            {error}
          </div>
        )}
        <div className="ar-form-actions mt-0">
          <Button variant="secondary" onClick={() => navigate(back)} disabled={cancel.isPending}>
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

/** /sales/:id/cancel (route requires sales.cancel_sale). */
export function CancelSalePage() {
  const sale = useSale(Number(useParams().id))
  return (
    <QueryState isPending={sale.isPending} error={sale.error}>
      {sale.data && <CancelForm sale={sale.data} />}
    </QueryState>
  )
}
