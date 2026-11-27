import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { useMemo, useReducer, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import type { Product } from '../../api/catalog'
import { toApiError, type ApiError, type FieldErrors } from '../../api/errors'
import { salesApi, type CheckoutRequest, type DraftCart, type Sale } from '../../api/sales'
import { useAuth } from '../../auth/useAuth'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { CheckboxField, MoneyField, SelectField, TextField } from '../../components/ui/fields'
import { useToast } from '../../components/ui/useToast'
import { formatDate, formatMoney, parseMoneyInput } from '../../lib/format'
import { compareMoney, isZero } from '../../lib/money'
import { productType } from '../products/productDisplay'
import { Cart } from './Cart'
import { cartReducer, cartTotals, initialCart, validateCart, type CartCustomer, type CartState, type CurrentProduct } from './cartReducer'
import { CustomerPicker } from './CustomerPicker'
import { invalidateAfterSale } from './hooks'
import { LeaveGuard } from './LeaveGuard'
import { ProductPicker } from './ProductPicker'
import { PAYMENT_METHODS, saleLabel, todayInStore } from './salesDisplay'

/** Server error keys → the editor field that shows them. */
function editorErrors(error: ApiError): { fields: FieldErrors; alert: string | null } {
  const fields: FieldErrors = {}
  const other = [...error.nonFieldErrors]
  const target = (key: string) => {
    if (key.startsWith('items')) return 'items'
    if (key === 'payment' || key.startsWith('payment.amount')) return 'amount_paid'
    if (key.startsWith('payment.payment_method')) return 'payment_method'
    if (['discount_amount', 'sale_date', 'backdate_reason', 'customer_id'].includes(key)) return key
    return null
  }
  for (const [key, messages] of Object.entries(error.fieldErrors)) {
    const field = target(key)
    if (field) fields[field] = [...(fields[field] ?? []), ...messages]
    else other.push(...messages)
  }
  const alert = other.length ? other.join(' ') : Object.keys(fields).length ? null : error.message
  return { fields, alert }
}

function draftBody(state: CartState): DraftCart {
  return {
    customer_id: state.customer?.id ?? null,
    items: state.lines.map((l) =>
      // Line discounts from a saved draft are sent back so they are never dropped.
      isZero(l.discount) ? { product_id: l.productId, quantity: l.quantity } : { product_id: l.productId, quantity: l.quantity, discount_amount: l.discount },
    ),
    discount_amount: parseMoneyInput(state.discount || '0') ?? '0.00',
  }
}

/** Notes for the staff member when a draft's products changed since it was saved. */
function draftChanges(draft: Sale, current: Record<number, CurrentProduct>): string[] {
  return draft.items.flatMap((item) => {
    const now = current[item.product]
    if (!now) return []
    if (!now.is_active) return [`${item.product_name} is no longer sold. Remove it to complete the sale.`]
    if (compareMoney(now.selling_price, item.unit_selling_price) !== 0)
      return [`${item.product_name} now costs ${formatMoney(now.selling_price)} (was ${formatMoney(item.unit_selling_price)}).`]
    return []
  })
}

export interface SaleEditorPageProps {
  /** Set when continuing a saved draft. */
  draft?: Sale
  draftCustomer?: CartCustomer | null
  /** Current catalog data for the draft's products (price and stock may have changed). */
  currentProducts?: Record<number, CurrentProduct>
}

/** Create Sale (/sales/new) and draft editing: product grid, cart, customer, payment. */
export function SaleEditorPage({ draft, draftCustomer = null, currentProducts = {} }: SaleEditorPageProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { hasPermission } = useAuth()
  const canPay = hasPermission('sales.record_payment')
  const canBackdate = hasPermission('sales.backdate_sale')
  // Re-checked on submit, so a screen left open past midnight uses the new day.
  const [today, setToday] = useState(todayInStore)
  const [state, dispatch] = useReducer(cartReducer, today, (t) =>
    draft
      ? cartReducer(initialCart(t), { type: 'loadDraft', sale: draft, customer: draftCustomer, current: currentProducts })
      : initialCart(t),
  )
  // What was last saved (or loaded); unsaved changes are measured against it.
  const [savedCart, setSavedCart] = useState(() => JSON.stringify(draftBody(state)))
  const isDirty = JSON.stringify(draftBody(state)) !== savedCart && state.lines.length > 0
  const changes = useMemo(() => (draft ? draftChanges(draft, currentProducts) : []), [draft, currentProducts])
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)
  const leaving = useRef(false)
  const totals = cartTotals(state)
  const inCart = Object.fromEntries(state.lines.map((l) => [l.productId, l.quantity]))
  const backdated = state.saleDate < today

  const finish = (sale: Sale, message: string) => {
    leaving.current = true
    toast.success(message)
    navigate(`/sales/${sale.id}`)
  }
  /** The date to submit: if the day rolled over while the page was open, use the new day. */
  const effectiveDate = () => {
    const now = todayInStore()
    if (now === today) return { now, saleDate: state.saleDate }
    setToday(now)
    const saleDate = state.saleDate === today ? now : state.saleDate
    if (saleDate !== state.saleDate) dispatch({ type: 'setSaleDate', value: saleDate })
    return { now, saleDate }
  }
  const fail = (error: unknown) => {
    const { fields, alert: text } = editorErrors(toApiError(error))
    setErrors(fields)
    setAlert(text)
  }

  const checkout = useMutation({
    mutationFn: (body: CheckoutRequest) => salesApi.checkout(body),
    onSuccess: async (sale) => {
      await invalidateAfterSale(queryClient)
      const outcome = sale.status === 'COMPLETED' ? 'completed' : 'saved as Pending Payment'
      finish(sale, `Sale ${saleLabel(sale)} ${outcome} — balance ${formatMoney(sale.balance)}.`)
    },
    onError: fail,
  })

  const saveDraft = useMutation({
    mutationFn: (body: DraftCart) => (state.draftId ? salesApi.replaceDraft(state.draftId, body) : salesApi.saveDraft(body)),
    onSuccess: async (sale, body) => {
      await invalidateAfterSale(queryClient)
      if (state.draftId) {
        // Same page stays open: later edits must be guarded again.
        setSavedCart(JSON.stringify(body))
        toast.success(`${saleLabel(sale)} saved.`)
      } else {
        finish(sale, `${saleLabel(sale)} saved.`)
      }
    },
    onError: fail,
  })

  const busy = checkout.isPending || saveDraft.isPending
  const complete = () => {
    if (busy) return
    const { now, saleDate } = effectiveDate()
    const current = { ...state, saleDate }
    const found = validateCart(current, { today: now, canBackdate })
    setErrors(found)
    setAlert(null)
    if (Object.keys(found).length > 0) return
    const paid = parseMoneyInput(state.amountPaid)
    checkout.mutate({
      ...draftBody(state),
      client_transaction_id: state.clientTransactionId,
      draft_id: state.draftId,
      sale_date: saleDate,
      backdate_reason: saleDate < now ? state.backdateReason.trim() : '',
      payment: state.paymentMethod && paid ? { payment_method: state.paymentMethod, amount: paid } : null,
    })
  }
  const draftSave = () => {
    if (busy) return
    const found = validateCart({ ...state, amountPaid: '', paymentMethod: '', saleDate: today }, { today, canBackdate })
    setErrors(found)
    setAlert(null)
    if (Object.keys(found).length === 0) saveDraft.mutate(draftBody(state))
  }
  const addProduct = (product: Product) =>
    dispatch({ type: 'add', product: { ...product, typeLabel: productType(product) } })

  return (
    <Card
      className="ar-page ar-sale-editor"
      title={draft ? saleLabel(draft) : undefined}
      aside={draft ? <span>Started {formatDate(draft.created_at)} by {draft.created_by_name}</span> : undefined}
    >
      <LeaveGuard when={() => isDirty && !leaving.current} message="The cart hasn't been saved. Leave and lose it?" />
      {changes.length > 0 && (
        <div className="mb-3">
          <Banner>
            <p className="mb-1 fw-semibold">Some products changed since this draft was saved. The sale uses current prices:</p>
            <ul className="mb-0">
              {changes.map((change) => (
                <li key={change}>{change}</li>
              ))}
            </ul>
          </Banner>
        </div>
      )}
      <div className="ar-sale-editor__fields">
        <div>
          <p className="form-label mb-1">Customer</p>
          <CustomerPicker value={state.customer} onChange={(customer) => dispatch({ type: 'setCustomer', customer })} />
          {errors.customer_id && <p className="invalid-feedback d-block">{errors.customer_id.join(' ')}</p>}
        </div>
        <div>
          <TextField
            label="Date of Sale"
            name="sale_date"
            type="date"
            max={today}
            value={state.saleDate}
            onChange={(value) => dispatch({ type: 'setSaleDate', value })}
            readOnly={!canBackdate}
            error={errors.sale_date}
            hint={canBackdate ? 'Past dates need a reason.' : undefined}
          />
          {canBackdate && (
            <CheckboxField
              name="set_today"
              label="Set to today"
              checked={state.saleDate === today}
              onChange={(checked) => checked && dispatch({ type: 'setSaleDate', value: today })}
            />
          )}
        </div>
        {canPay ? (
          <>
            <SelectField
              label="Payment Method"
              name="payment_method"
              value={state.paymentMethod}
              onChange={(value) => dispatch({ type: 'setPaymentMethod', value: value as CartState['paymentMethod'] })}
              options={PAYMENT_METHODS}
              placeholder="No payment yet"
              error={errors.payment_method}
            />
            <MoneyField
              label="Amount Paid"
              name="amount_paid"
              value={state.amountPaid}
              onChange={(value) => dispatch({ type: 'setAmountPaid', value })}
              placeholder="0.00"
              error={errors.amount_paid}
              hint={state.amountPaid ? `Balance after payment: ${formatMoney(totals.balance)}` : undefined}
            />
          </>
        ) : (
          <div className="ar-sale-editor__wide">
            <Banner tone="info">You can't record payments. The sale will be saved as Pending Payment for collection.</Banner>
          </div>
        )}
        {backdated && canBackdate && (
          <TextField
            label="Reason for past date"
            name="backdate_reason"
            value={state.backdateReason}
            onChange={(value) => dispatch({ type: 'setBackdateReason', value })}
            placeholder="Required: e.g. entering a paper receipt"
            error={errors.backdate_reason}
            className="ar-sale-editor__wide"
            required
          />
        )}
      </div>

      <div className="ar-sale-editor__body">
        <ProductPicker inCart={inCart} onAdd={addProduct} />
        <div className="ar-sale-editor__side">
          <Cart
            lines={state.lines}
            totals={totals}
            error={errors.items}
            onQuantity={(productId, quantity) => dispatch({ type: 'setQuantity', productId, quantity })}
            onRemove={(productId) => dispatch({ type: 'remove', productId })}
          />
          <MoneyField
            label="Discount"
            name="discount_amount"
            value={state.discount}
            onChange={(value) => dispatch({ type: 'setDiscount', value })}
            placeholder="0.00"
            error={errors.discount_amount}
          />
          {alert && (
            <div className="alert alert-danger ar-alert" role="alert">
              {alert}
            </div>
          )}
          <Button className="w-100" busy={checkout.isPending} disabled={saveDraft.isPending} onClick={complete}>
            Complete sale
          </Button>
          <Button className="w-100" variant="secondary" icon={Save} busy={saveDraft.isPending} disabled={checkout.isPending} onClick={draftSave}>
            Save draft
          </Button>
        </div>
      </div>
    </Card>
  )
}
