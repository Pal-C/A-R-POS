import { useState } from 'react'
import type { Product } from '../../api/catalog'
import { Button } from '../../components/ui/Button'
import { TextAreaField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { ProductSummary } from './ProductSummary'

export interface ReactivateProductDialogProps {
  product: Product
  onConfirm: (reason: string) => void
  onClose: () => void
  busy: boolean
  error?: string | null
}

export function ReactivateProductDialog({ product, onConfirm, onClose, busy, error }: ReactivateProductDialogProps) {
  const [reason, setReason] = useState('')
  return (
    <Modal
      open
      title="Reactivate Product"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button busy={busy} disabled={!reason.trim()} onClick={() => onConfirm(reason.trim())}>
            Reactivate product
          </Button>
        </>
      }
    >
      <ProductSummary product={product} />
      <p className="mb-0 text-body-secondary">The product becomes sellable again in POS.</p>
      <TextAreaField
        label="Reason for reactivation"
        name="reason"
        value={reason}
        onChange={setReason}
        placeholder="Required: e.g. back in the supplier's range"
        required
      />
      {error && (
        <div className="alert alert-danger ar-alert" role="alert">
          {error}
        </div>
      )}
    </Modal>
  )
}
