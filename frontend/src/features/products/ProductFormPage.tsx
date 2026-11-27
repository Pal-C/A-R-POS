import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { productsApi, type ProductDetail } from '../../api/catalog'
import { toApiError, type FieldErrors } from '../../api/errors'
import { useAuth } from '../../auth/useAuth'
import { QueryState } from '../../components/QueryState'
import { Card } from '../../components/ui/Card'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useToast } from '../../components/ui/useToast'
import { formatDate } from '../../lib/format'
import { splitApiError } from './errorDisplay'
import { invalidateProducts, useProduct } from './hooks'
import { ProductForm } from './ProductForm'
import {
  diffProduct,
  emptyProductForm,
  formFromProduct,
  toCreatePayload,
  validateProductForm,
  type ProductFormValues,
} from './productFormModel'

/** Server keys shown next to a form field; anything else goes to the alert. */
const FORM_FIELDS = [
  'name',
  'category',
  'subcategory',
  'brand',
  'model',
  'variant_description',
  'supplier',
  'cost_price',
  'selling_price',
  'stock_quantity',
  'low_stock_threshold',
  'sku',
  'reason',
]

const FIELD_LABELS: Record<string, string> = {
  name: 'Product Name',
  category: 'Category',
  subcategory: 'Type',
  brand: 'Brand',
  model: 'Model',
  variant_description: 'Size / Variant',
  supplier: 'Supplier',
  cost_price: 'Cost of Sale',
  selling_price: 'Selling Price',
  stock_quantity: 'Stock Quantity',
  low_stock_threshold: 'Low-stock Threshold',
  sku: 'Barcode / SKU',
  is_active: 'Active',
}

function usePermissions() {
  const { hasPermission } = useAuth()
  return {
    canViewCost: hasPermission('catalog.view_product_cost'),
    canAdjustStock: hasPermission('catalog.adjust_stock'),
  }
}

function errorAlert(message: string) {
  return (
    <div className="alert alert-danger ar-alert" role="alert">
      {message}
    </div>
  )
}

function AddProduct() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { canViewCost, canAdjustStock } = usePermissions()
  const [values, setValues] = useState(emptyProductForm)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => productsApi.create(toCreatePayload(values, canViewCost)),
    onSuccess: async (product) => {
      await invalidateProducts(queryClient)
      toast.success(`${product.name} saved with ${product.stock_quantity} in stock.`)
      navigate('/inventory')
    },
    onError: (error) => {
      const { fieldErrors, alert } = splitApiError(toApiError(error), FORM_FIELDS, { initial_stock: 'stock_quantity' })
      setErrors(fieldErrors)
      setAlert(alert)
    },
  })

  const submit = () => {
    const found = validateProductForm(values, { mode: 'add', canViewCost })
    setErrors(found)
    setAlert(null)
    if (Object.keys(found).length === 0) create.mutate()
  }

  return (
    <Card title="New product" className="ar-page ar-form-card">
      <ProductForm
        mode="add"
        values={values}
        errors={errors}
        onChange={setValues}
        onSubmit={submit}
        onCancel={() => navigate('/inventory')}
        canViewCost={canViewCost}
        canAdjustStock={canAdjustStock}
        saving={create.isPending}
        hasChanges
        alert={alert && errorAlert(alert)}
      />
    </Card>
  )
}

function EditProduct({ product, onReload }: { product: ProductDetail; onReload: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const permissions = usePermissions()
  const [initial] = useState(() => formFromProduct(product))
  const [values, setValues] = useState<ProductFormValues>(initial)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)
  const [conflict, setConflict] = useState<Record<string, unknown> | null>(null)
  const { changes, expected } = diffProduct(initial, values, permissions)
  const hasChanges = Object.keys(changes).length > 0

  const update = useMutation({
    mutationFn: () => productsApi.update(product.id, { changes, expected, reason: values.reason.trim() }),
    onSuccess: async (saved) => {
      await invalidateProducts(queryClient)
      toast.success(`${saved.name} updated.`)
      navigate('/inventory')
    },
    onError: (error) => {
      const apiError = toApiError(error)
      if (apiError.kind === 'conflict') {
        setConflict(apiError.current ?? {})
        return
      }
      const { fieldErrors, alert } = splitApiError(apiError, FORM_FIELDS)
      setErrors(fieldErrors)
      setAlert(alert)
    },
  })

  const submit = () => {
    const found = validateProductForm(values, { mode: 'edit', canViewCost: permissions.canViewCost })
    setErrors(found)
    setAlert(null)
    setConflict(null)
    if (Object.keys(found).length === 0 && hasChanges) update.mutate()
  }

  const lastEvent = product.last_event
  const conflictAlert = conflict && (
    <div className="alert alert-warning ar-alert" role="alert">
      <p className="mb-1 fw-semibold">This product was changed by someone else while you were editing.</p>
      <ul className="mb-2">
        {Object.entries(conflict).map(([field, value]) => (
          <li key={field}>
            {FIELD_LABELS[field] ?? field} is now <strong>{String(value)}</strong>
          </li>
        ))}
      </ul>
      <button type="button" className="btn btn-link p-0" onClick={onReload}>
        Load the latest values (your edits will be discarded)
      </button>
    </div>
  )

  return (
    <Card
      title="Product details"
      className="ar-page ar-form-card"
      aside={
        <>
          {lastEvent && (
            <span>
              Last updated {formatDate(lastEvent.created_at)} by {lastEvent.performed_by.display_name}
            </span>
          )}
          <StatusBadge domain="product" value={product.is_active ? 'active' : 'inactive'} />
        </>
      }
    >
      <ProductForm
        mode="edit"
        values={values}
        errors={errors}
        onChange={setValues}
        onSubmit={submit}
        onCancel={() => navigate('/inventory')}
        {...permissions}
        saving={update.isPending}
        hasChanges={hasChanges}
        alert={conflictAlert || (alert && errorAlert(alert))}
      />
    </Card>
  )
}

/** /inventory/new and /inventory/:id/edit */
export function ProductFormPage() {
  const { id } = useParams()
  const productId = id ? Number(id) : undefined
  const product = useProduct(productId)
  const [formKey, setFormKey] = useState(0)

  if (productId === undefined) return <AddProduct />
  return (
    <QueryState isPending={product.isPending} error={product.error}>
      {product.data && (
        <EditProduct
          key={`${product.data.id}-${formKey}`}
          product={product.data}
          onReload={async () => {
            await product.refetch()
            setFormKey((k) => k + 1)
          }}
        />
      )}
    </QueryState>
  )
}
