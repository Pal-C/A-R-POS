import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toApiError } from '../../api/errors'
import { salesApi, type Sale } from '../../api/sales'
import { Button } from '../../components/ui/Button'
import { TextAreaField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { useToast } from '../../components/ui/useToast'
import type { CartCustomer } from './cartReducer'
import { CustomerPicker } from '../../components/CustomerPicker'
import { invalidateAfterSale } from './hooks'
import { saleLabel } from './salesDisplay'

/** Links (or changes) the customer of a finalized sale, with a logged reason. */
export function AssociateCustomerDialog({ sale, onClose }: { sale: Sale; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [customer, setCustomer] = useState<CartCustomer | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const change = useMutation({
    mutationFn: () => salesApi.changeCustomer(sale.id, { customer_id: customer!.id, reason: reason.trim() }),
    onSuccess: async (updated) => {
      await invalidateAfterSale(queryClient)
      toast.success(`${updated.customer_name} is now linked to ${saleLabel(sale)}.`)
      onClose()
    },
    onError: (e) => {
      const apiError = toApiError(e)
      setError([...apiError.nonFieldErrors, ...Object.values(apiError.fieldErrors).flat()].join(' ') || apiError.message)
    },
  })

  const ready = !!customer && reason.trim().length > 0
  return (
    <Modal
      open
      title={sale.customer ? 'Change Customer' : 'Associate Customer'}
      onClose={onClose}
      busy={change.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={change.isPending}>
            Cancel
          </Button>
          <Button busy={change.isPending} disabled={!ready} onClick={() => change.mutate()}>
            Link customer
          </Button>
        </>
      }
    >
      <CustomerPicker value={customer} onChange={setCustomer} />
      <TextAreaField label="Reason for change" name="reason" value={reason} onChange={setReason} placeholder="Required: e.g. customer asked for a receipt" required />
      {error && (
        <div className="alert alert-danger ar-alert" role="alert">
          {error}
        </div>
      )}
    </Modal>
  )
}
