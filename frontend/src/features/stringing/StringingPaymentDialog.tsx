import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { PaymentMethod } from '../../api/common'
import { toApiError, type FieldErrors } from '../../api/errors'
import { stringingApi, type StringingOrder } from '../../api/stringing'
import { Button } from '../../components/ui/Button'
import { MoneyField, SelectField, TextField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { useToast } from '../../components/ui/useToast'
import { formatMoney, parseMoneyInput } from '../../lib/format'
import { compareMoney, toCents } from '../../lib/money'
import { PAYMENT_METHODS } from '../../lib/payments'
import { invalidateAfterStringing } from './hooks'

export type PaymentMode = 'receipt' | 'refund'

/** Records a receipt toward the balance, or a refund on a cancelled order (FR-015). */
export function StringingPaymentDialog({ order, mode, onClose }: { order: StringingOrder; mode: PaymentMode; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const refund = mode === 'refund'
  const limit = refund ? order.refund_due : order.balance
  const [amount, setAmount] = useState(limit)
  const [method, setMethod] = useState<PaymentMethod | ''>('')
  const [reference, setReference] = useState('')
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)

  const record = useMutation({
    mutationFn: (value: string) =>
      stringingApi.recordPayment(order.id, {
        payment_type: refund ? 'REFUND' : 'RECEIPT',
        amount: value,
        payment_method: method as PaymentMethod,
        reference_number: reference.trim(),
        reason: refund ? reason.trim() : undefined,
      }),
    onSuccess: async ({ order: updated }) => {
      await invalidateAfterStringing(queryClient)
      toast.success(
        refund
          ? `Refund recorded for ${order.order_number}. Refund due is now ${formatMoney(updated.refund_due)}.`
          : `Payment recorded for ${order.order_number}. Balance is now ${formatMoney(updated.balance)}.`,
      )
      onClose()
    },
    onError: (error) => {
      const apiError = toApiError(error)
      setErrors(apiError.fieldErrors)
      setAlert(apiError.nonFieldErrors.join(' ') || (Object.keys(apiError.fieldErrors).length ? null : apiError.message))
    },
  })

  const submit = () => {
    const found: FieldErrors = {}
    const value = parseMoneyInput(amount)
    if (!method) found.payment_method = [refund ? 'Choose how the money is returned.' : 'Choose how the customer paid.']
    if (value === null || toCents(value) <= 0n) found.amount = ['Enter an amount more than 0.']
    else if (compareMoney(value, limit) > 0) found.amount = [`Amount can't be more than ${refund ? 'the refund due' : 'the balance'} of ${formatMoney(limit)}.`]
    if (refund && !reason.trim()) found.reason = ['Enter a reason for the refund.']
    setErrors(found)
    setAlert(null)
    if (Object.keys(found).length === 0 && value) record.mutate(value)
  }

  return (
    <Modal
      open
      title={refund ? 'Record Refund' : 'Record Payment'}
      onClose={onClose}
      busy={record.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={record.isPending}>
            Cancel
          </Button>
          <Button busy={record.isPending} onClick={submit}>
            {refund ? 'Record refund' : 'Record payment'}
          </Button>
        </>
      }
    >
      <div className="d-grid gap-3">
        <p className="mb-0">
          {order.order_number}: {refund ? 'refund due' : 'balance'} {formatMoney(limit)}
        </p>
        <MoneyField label="Amount" name="amount" value={amount} onChange={setAmount} error={errors.amount} required />
        <SelectField
          label="Payment Method"
          name="payment_method"
          value={method}
          onChange={(value) => setMethod(value as PaymentMethod | '')}
          options={PAYMENT_METHODS}
          placeholder="Select method"
          error={errors.payment_method}
          required
        />
        <TextField label="Reference #" name="reference_number" value={reference} onChange={setReference} error={errors.reference_number} maxLength={100} />
        {refund && <TextField label="Reason" name="reason" value={reason} onChange={setReason} error={errors.reason} required />}
        {alert && (
          <div className="alert alert-danger ar-alert mb-0" role="alert">
            {alert}
          </div>
        )}
      </div>
    </Modal>
  )
}
