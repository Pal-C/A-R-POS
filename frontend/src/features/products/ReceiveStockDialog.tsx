import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { productKeys, productsApi, type Product } from '../../api/catalog'
import type { FieldErrors } from '../../api/errors'
import { Button } from '../../components/ui/Button'
import { NumberField, SelectField, TextField } from '../../components/ui/fields'
import { Modal } from '../../components/ui/Modal'
import { SearchBox } from '../../components/ui/SearchBox'
import { ProductSummary } from './ProductSummary'

export interface ReceiveStockValues {
  product: Product
  quantity: number
  referenceNumber: string
}

export interface ReceiveStockDialogProps {
  product?: Product
  onConfirm: (values: ReceiveStockValues) => void
  onClose: () => void
  busy: boolean
  error?: string | null
  serverErrors?: FieldErrors
}

/** Records a supplier delivery as a restock movement. */
export function ReceiveStockDialog({ product: preselected, onConfirm, onClose, busy, error, serverErrors = {} }: ReceiveStockDialogProps) {
  const [search, setSearch] = useState('')
  // Keep the chosen product itself, so a new search can't make the choice disappear.
  const [chosen, setChosen] = useState<Product | undefined>(preselected)
  const [quantity, setQuantity] = useState('')
  const [reference, setReference] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})

  const params = { search: search || undefined, is_active: true }
  const choices = useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => productsApi.list(params),
    enabled: !preselected,
  })
  const results = choices.data?.results ?? []
  const options = chosen && !results.some((p) => p.id === chosen.id) ? [chosen, ...results] : results
  const selected = chosen

  const submit = () => {
    const found: FieldErrors = {}
    if (!selected) found.product = ['Choose a product.']
    if (!/^\d+$/.test(quantity.trim()) || Number(quantity) < 1) found.quantity_received = ['Enter a quantity of 1 or more.']
    setErrors(found)
    if (selected && Object.keys(found).length === 0) {
      onConfirm({ product: selected, quantity: Number(quantity), referenceNumber: reference.trim() })
    }
  }

  return (
    <Modal
      open
      title="Receive Stock"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button busy={busy} onClick={submit}>
            Receive stock
          </Button>
        </>
      }
    >
      {preselected ? (
        <ProductSummary product={preselected} />
      ) : (
        <>
          <SearchBox value={search} onChange={setSearch} placeholder="Find a product" />
          <SelectField
            label="Product"
            name="product"
            value={chosen ? String(chosen.id) : ''}
            onChange={(id) => setChosen(options.find((p) => String(p.id) === id))}
            options={options.map((p) => ({ value: String(p.id), label: `${p.name} (${p.sku}) — stock ${p.stock_quantity}` }))}
            placeholder={choices.isPending ? 'Loading products…' : 'Select a product'}
            error={errors.product}
            required
          />
        </>
      )}
      <NumberField
        label="Quantity received"
        name="quantity_received"
        value={quantity}
        onChange={setQuantity}
        error={errors.quantity_received ?? serverErrors.quantity_received}
        required
      />
      <TextField
        label="Reference number"
        name="reference_number"
        value={reference}
        onChange={setReference}
        hint="Optional, e.g. supplier delivery receipt"
        error={serverErrors.reference_number}
      />
      {error && (
        <div className="alert alert-danger ar-alert" role="alert">
          {error}
        </div>
      )}
    </Modal>
  )
}
