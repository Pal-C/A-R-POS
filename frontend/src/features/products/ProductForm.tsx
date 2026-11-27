import type { FormEvent, ReactNode } from 'react'
import { PRODUCT_CATEGORIES } from '../../api/catalog'
import type { FieldErrors } from '../../api/errors'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { CheckboxField, MoneyField, NumberField, SelectField, TextField } from '../../components/ui/fields'
import type { ProductFormValues } from './productFormModel'

export interface ProductFormProps {
  mode: 'add' | 'edit'
  values: ProductFormValues
  errors: FieldErrors
  onChange: (values: ProductFormValues) => void
  onSubmit: () => void
  onCancel: () => void
  canViewCost: boolean
  canAdjustStock: boolean
  saving: boolean
  /** Edit: Save stays disabled until something changed. */
  hasChanges: boolean
  /** Alert shown above the actions (e.g. conflict or permission errors). */
  alert?: ReactNode
}

/** Add/Edit Product fields in the reference layout (3-column grid). */
export function ProductForm({
  mode,
  values,
  errors,
  onChange,
  onSubmit,
  onCancel,
  canViewCost,
  canAdjustStock,
  saving,
  hasChanges,
  alert,
}: ProductFormProps) {
  const set = <K extends keyof ProductFormValues>(field: K) => (value: ProductFormValues[K]) =>
    onChange({ ...values, [field]: value })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="ar-form-grid">
        <TextField label="Product Name" name="name" value={values.name} onChange={set('name')} error={errors.name} placeholder="Product name" required />
        <SelectField
          label="Category"
          name="category"
          value={values.category}
          onChange={set('category')}
          error={errors.category}
          options={PRODUCT_CATEGORIES}
          placeholder="Select category"
          required
        />
        <TextField label="Type" name="subcategory" value={values.subcategory} onChange={set('subcategory')} error={errors.subcategory} placeholder="e.g. String, Overgrip" />
        <TextField label="Brand" name="brand" value={values.brand} onChange={set('brand')} error={errors.brand} placeholder="Brand" />
        <TextField label="Model" name="model" value={values.model} onChange={set('model')} error={errors.model} placeholder="Model" />
        <TextField label="Size / Variant" name="variant_description" value={values.variant_description} onChange={set('variant_description')} error={errors.variant_description} placeholder="Size" />
        <TextField label="Supplier" name="supplier" value={values.supplier} onChange={set('supplier')} error={errors.supplier} placeholder="Supplier" />
        {canViewCost && (
          <MoneyField label="Cost of Sale" name="cost_price" value={values.cost_price} onChange={set('cost_price')} error={errors.cost_price} placeholder="0.00" required />
        )}
        <MoneyField label="Selling Price" name="selling_price" value={values.selling_price} onChange={set('selling_price')} error={errors.selling_price} placeholder="0.00" required />
        <NumberField
          label={mode === 'add' ? 'Starting Stock' : 'Stock Quantity'}
          name="stock_quantity"
          value={values.stock_quantity}
          onChange={set('stock_quantity')}
          error={errors.stock_quantity}
          readOnly={mode === 'edit' && !canAdjustStock}
          hint={mode === 'edit' && !canAdjustStock ? 'Ask a manager to adjust stock.' : undefined}
        />
        <NumberField label="Low-stock Threshold" name="low_stock_threshold" value={values.low_stock_threshold} onChange={set('low_stock_threshold')} error={errors.low_stock_threshold} placeholder="e.g. 5" />
        <TextField label="Barcode / SKU" name="sku" value={values.sku} onChange={set('sku')} error={errors.sku} placeholder="e.g. YNX-BG66-UM" required />
        <div className="align-self-end">
          <CheckboxField
            label="Product is active and sellable"
            name="is_active"
            checked={values.is_active}
            onChange={set('is_active')}
            disabled={mode === 'edit'}
          />
          {mode === 'edit' && (
            <p className="form-text mb-0">Use Remove or Reactivate in the product list to change this.</p>
          )}
        </div>
        {mode === 'edit' && (
          <TextField
            label="Reason for change"
            name="reason"
            value={values.reason}
            onChange={set('reason')}
            error={errors.reason}
            placeholder="Required: why are these details being updated?"
            className="ar-form-grid__wide"
            required
          />
        )}
        <div className="ar-form-grid__wide">
          <Banner>
            {mode === 'add'
              ? 'The product appears in POS once saved. Starting stock is logged as an inventory increase.'
              : 'Price and stock changes are recorded in the audit log with your name and the time.'}
          </Banner>
        </div>
      </div>
      {alert && <div className="mt-3">{alert}</div>}
      <div className="ar-form-actions">
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" busy={saving} disabled={mode === 'edit' && !hasChanges}>
          {mode === 'add' ? 'Save product' : 'Save changes'}
        </Button>
      </div>
    </form>
  )
}
