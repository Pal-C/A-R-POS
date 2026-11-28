import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { PaymentMethod } from '../../api/common'
import { toApiError, type FieldErrors } from '../../api/errors'
import { salesApi, type Sale } from '../../api/sales'
import { Button } from '../../components/ui/Button'
import { MoneyField, SelectField, TextField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { useToast } from '../../components/ui/useToast'
import { formatMoney, parseMoneyInput } from '../../lib/format'
import { compareMoney, subtractMoney, toCents } from '../../lib/money'
import { invalidateAfterSale } from './hooks'
import { PAYMENT_METHODS } from '../../lib/payments'
import { saleLabel } from './salesDisplay'

/** Records a receipt toward a sale's outstanding balance. */
export function RecordPaymentDialog({ sale, onClose }: { sale: Sale; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [method, setMethod] = useState<PaymentMethod | ''>('')
  const [amount, setAmount] = useState(sale.balance)
  const [reference, setReference] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)

  const record = useMutation({
    mutationFn: (paid: string) =>
      salesApi.recordPayment({ sale: sale.id, amount: paid, payment_method: method as PaymentMethod, reference_number: reference.trim() }),
    onSuccess: async (_payment, paid) => {
      await invalidateAfterSale(queryClient)
      toast.success(`Payment recorded for ${saleLabel(sale)}. Balance is now ${formatMoney(subtractMoney(sale.balance, paid))}.`)
      onClose()
    },
    onError: (error) => {
      const apiError = toApiError(error)
      setErrors(apiError.fieldErrors)
      setAlert(apiError.message)
    },
  })

  const submit = () => {
    const found: FieldErrors = {}
    const paid = parseMoneyInput(amount)
    if (!method) found.payment_method = ['Choose how the customer paid.']
    if (paid === null || toCents(paid) <= 0n) found.amount = ['Enter an amount more than 0.']
    else if (compareMoney(paid, sale.balance) > 0) found.amount = [`Amount can't be more than the balance of ${formatMoney(sale.balance)}.`]
    setErrors(found)
    setAlert(null)
    if (Object.keys(found).length === 0 && paid) record.mutate(paid)
  }

  return (
    <Modal
      open
      title="Record Payment"
      onClose={onClose}
      busy={record.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={record.isPending}>
            Cancel
          </Button>
          <Button busy={record.isPending} onClick={submit}>
            Record payment
          </Button>
        </>
      }
    >
      <p className="mb-0">
        Outstanding balance: <strong>{formatMoney(sale.balance)}</strong>
      </p>
      <SelectField label="Payment Method" name="payment_method" value={method} onChange={(v) => setMethod(v as PaymentMethod | '')} options={PAYMENT_METHODS} placeholder="Select method" error={errors.payment_method} required />
      <MoneyField label="Amount" name="amount" value={amount} onChange={setAmount} error={errors.amount} required />
      <TextField label="Reference number" name="reference_number" value={reference} onChange={setReference} hint="Optional, e.g. GCash reference" />
      {alert && Object.keys(errors).length === 0 && (
        <div className="alert alert-danger ar-alert" role="alert">
          {alert}
        </div>
      )}
    </Modal>
  )
}
