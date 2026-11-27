import { useState } from 'react'
import type { Product } from '../../api/catalog'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { ConfirmCheck } from '../../components/ui/ConfirmCheck'
import { TextAreaField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { formatCount } from '../../lib/format'
import { ProductSummary } from './ProductSummary'

export interface RemoveProductDialogProps {
  product: Product
  onConfirm: (reason: string) => void
  onClose: () => void
  busy: boolean
  error?: string | null
}

/** Deactivates (never deletes) a product after a reason and an explicit confirmation. */
export function RemoveProductDialog({ product, onConfirm, onClose, busy, error }: RemoveProductDialogProps) {
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const ready = reason.trim().length > 0 && confirmed

  return (
    <Modal
      open
      title="Remove Product"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger-confirm" busy={busy} disabled={!ready} onClick={() => onConfirm(reason.trim())}>
            Remove product
          </Button>
        </>
      }
    >
      <ProductSummary product={product} />
      <p className="mb-0 text-body-secondary">
        The product is deactivated, not erased. Past sales keep their record and it can be restored later.
      </p>
      {product.stock_quantity > 0 && (
        <Banner>This product still has {formatCount(product.stock_quantity)} in stock. It will stay counted but can't be sold.</Banner>
      )}
      <TextAreaField
        label="Reason for removal"
        name="reason"
        value={reason}
        onChange={setReason}
        placeholder="Required: e.g. discontinued by supplier"
        required
      />
      <ConfirmCheck label="Are you sure? This hides the product from POS" checked={confirmed} onChange={setConfirmed} />
      {error && (
        <div className="alert alert-danger ar-alert" role="alert">
          {error}
        </div>
      )}
    </Modal>
  )
}
