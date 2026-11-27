import type { ProductCategory, ProductCreate, ProductDetail, ProductEditable } from '../../api/catalog'
import type { FieldErrors } from '../../api/errors'
import { parseMoneyInput } from '../../lib/format'

/** Form state; every value is a string so inputs stay controlled (data-model.md ProductFormValues). */
export interface ProductFormValues {
  name: string
  category: string
  subcategory: string
  brand: string
  model: string
  variant_description: string
  supplier: string
  cost_price: string
  selling_price: string
  stock_quantity: string
  low_stock_threshold: string
  sku: string
  is_active: boolean
  reason: string
}

export const emptyProductForm: ProductFormValues = {
  name: '',
  category: '',
  subcategory: '',
  brand: '',
  model: '',
  variant_description: '',
  supplier: '',
  cost_price: '',
  selling_price: '',
  stock_quantity: '0',
  low_stock_threshold: '5',
  sku: '',
  is_active: true,
  reason: '',
}

export function formFromProduct(product: ProductDetail): ProductFormValues {
  return {
    name: product.name,
    category: product.category,
    subcategory: product.subcategory,
    brand: product.brand,
    model: product.model,
    variant_description: product.variant_description,
    supplier: product.supplier,
    cost_price: product.cost_price ?? '',
    selling_price: product.selling_price,
    stock_quantity: String(product.stock_quantity),
    low_stock_threshold: String(product.low_stock_threshold),
    sku: product.sku,
    is_active: product.is_active,
    reason: '',
  }
}

const isWholeNumber = (raw: string) => /^\d+$/.test(raw.trim())

interface ValidateOptions {
  mode: 'add' | 'edit'
  canViewCost: boolean
}

/** Client-side checks mirroring the server rules; the server stays authoritative. */
export function validateProductForm(values: ProductFormValues, { mode, canViewCost }: ValidateOptions): FieldErrors {
  const errors: FieldErrors = {}
  if (!values.name.trim()) errors.name = ['Enter a product name.']
  if (!values.category) errors.category = ['Choose a category.']
  if (!values.sku.trim()) errors.sku = ['Enter a barcode or SKU.']
  if (parseMoneyInput(values.selling_price) === null) errors.selling_price = ['Enter a price like 450 or 450.00.']
  if (canViewCost && parseMoneyInput(values.cost_price) === null) errors.cost_price = ['Enter a cost like 320 or 320.00.']
  if (!isWholeNumber(values.stock_quantity)) errors.stock_quantity = ['Enter a whole number, 0 or more.']
  if (!isWholeNumber(values.low_stock_threshold)) errors.low_stock_threshold = ['Enter a whole number, 0 or more.']
  if (mode === 'edit' && !values.reason.trim()) errors.reason = ['Explain why these details are being updated.']
  return errors
}

const TEXT_FIELDS = ['name', 'subcategory', 'brand', 'model', 'variant_description', 'supplier', 'sku'] as const

/** Typed API values for the editable fields present in the form. */
function typedValues(values: ProductFormValues, canViewCost: boolean): ProductEditable {
  const typed: ProductEditable = {
    category: values.category as ProductCategory,
    selling_price: parseMoneyInput(values.selling_price) ?? values.selling_price,
    low_stock_threshold: Number(values.low_stock_threshold),
    is_active: values.is_active,
    stock_quantity: Number(values.stock_quantity),
  }
  for (const field of TEXT_FIELDS) typed[field] = values[field].trim()
  if (canViewCost) typed.cost_price = parseMoneyInput(values.cost_price) ?? values.cost_price
  return typed
}

export function toCreatePayload(values: ProductFormValues, canViewCost: boolean): ProductCreate {
  const { stock_quantity, ...fields } = typedValues(values, canViewCost)
  return { ...(fields as ProductCreate), initial_stock: stock_quantity }
}

/**
 * The fields that differ from what the editor loaded, plus their original values,
 * for the server's per-field conflict check (research R7).
 */
export function diffProduct(
  initial: ProductFormValues,
  current: ProductFormValues,
  { canViewCost, canAdjustStock }: { canViewCost: boolean; canAdjustStock: boolean },
): { changes: ProductEditable; expected: ProductEditable } {
  const before = typedValues(initial, canViewCost)
  const after = typedValues(current, canViewCost)
  // Activation goes through Remove/Reactivate (own confirmation and history entry).
  delete before.is_active
  delete after.is_active
  if (!canAdjustStock) {
    delete before.stock_quantity
    delete after.stock_quantity
  }
  const changes: Record<string, unknown> = {}
  const expected: Record<string, unknown> = {}
  for (const key of Object.keys(after) as Array<keyof ProductEditable>) {
    if (after[key] !== before[key]) {
      changes[key] = after[key]
      expected[key] = before[key]
    }
  }
  return { changes: changes as ProductEditable, expected: expected as ProductEditable }
}
