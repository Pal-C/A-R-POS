import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useReducer, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toApiError, type FieldErrors } from '../../api/errors'
import { stringingApi, type StringingOrder } from '../../api/stringing'
import { useAuth } from '../../auth/useAuth'
import { CustomerPicker } from '../../components/CustomerPicker'
import { LeaveGuard } from '../../components/LeaveGuard'
import { QueryState } from '../../components/QueryState'
import { Banner } from '../../components/ui/Banner'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { CheckboxField, MoneyField, SelectField, TextAreaField, TextField } from '../../components/ui/fields'
import { useToast } from '../../components/ui/useToast'
import { config } from '../../config'
import { formatMoney } from '../../lib/format'
import { PAYMENT_METHODS } from '../../lib/payments'
import { invalidateAfterStringing, useStringingOrder } from './hooks'
import { InvoiceLines } from './InvoicePanel'
import {
  formFieldFor,
  initialOrderForm,
  orderFormFromOrder,
  orderFormReducer,
  orderTotals,
  toCreateBody,
  toUpdateBody,
  validateOrder,
  type OrderFormState,
  type OrderTextField,
} from './orderForm'
import { isOpen } from './stringingDisplay'

/** Everything the staff member typed, without the idempotency key. */
const snapshot = (state: OrderFormState) => JSON.stringify({ ...state, clientTransactionId: '' })

function OrderForm({ order }: { order?: StringingOrder }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  const { hasPermission } = useAuth()
  // Deposits are taken on create only; later payments go through Details.
  const withDeposit = !order && hasPermission('sales.record_payment')
  const [state, dispatch] = useReducer(orderFormReducer, order, (o) => (o ? orderFormFromOrder(o) : initialOrderForm()))
  const [initial] = useState(() => snapshot(state))
  const [errors, setErrors] = useState<FieldErrors>({})
  const [alert, setAlert] = useState<string | null>(null)
  const leaving = useRef(false)
  const totals = orderTotals(state)
  const discountHint = `Shop default ${formatMoney(config.stringingDefaults.storeStringDiscount)}`

  const done = (saved: StringingOrder, message: string) => {
    leaving.current = true
    toast.success(message)
    navigate(`/stringing?order=${saved.id}`)
  }
  const fail = (error: unknown) => {
    const apiError = toApiError(error)
    const fields: FieldErrors = {}
    const other = [...apiError.nonFieldErrors]
    for (const [key, messages] of Object.entries(apiError.fieldErrors)) {
      const field = formFieldFor(key)
      if (field) fields[field] = [...(fields[field] ?? []), ...messages]
      else other.push(...messages)
    }
    setErrors(fields)
    setAlert(other.length ? other.join(' ') : Object.keys(fields).length ? null : apiError.message)
  }

  const save = useMutation({
    mutationFn: async () => {
      if (!order) return stringingApi.create(toCreateBody(state, { withDeposit }))
      const changes = toUpdateBody(state, order)
      return Object.keys(changes).length ? stringingApi.update(order.id, changes) : order
    },
    onSuccess: async (saved) => {
      await invalidateAfterStringing(queryClient)
      if (order) done(saved, `Order ${saved.order_number} updated.`)
      else done(saved, `Order ${saved.order_number} created. Balance due ${formatMoney(saved.balance)}.`)
    },
    onError: fail,
  })

  const submit = () => {
    if (save.isPending) return
    const found = validateOrder(state, { withDeposit })
    setErrors(found)
    setAlert(null)
    if (Object.keys(found).length === 0) save.mutate()
  }
  const text = (field: OrderTextField) => (value: string) => dispatch({ type: 'set', field, value })
  const back = order ? `/stringing?order=${order.id}` : '/stringing'

  return (
    <div className="ar-page ar-stringing-form">
      <LeaveGuard
        when={() => !leaving.current && snapshot(state) !== initial}
        title="Leave this order?"
        message="Your changes to this stringing order haven't been saved. Leave and lose them?"
      />
      <Card title={order ? `Order ${order.order_number}` : 'Order Details'} className="ar-stringing-form__details">
        <div className="ar-form-grid">
          <div className="ar-form-grid__wide">
            <p className="form-label mb-1">Customer</p>
            <CustomerPicker value={state.customer} onChange={(customer) => dispatch({ type: 'setCustomer', customer })} />
            {errors.customer && <p className="invalid-feedback d-block">{errors.customer.join(' ')}</p>}
          </div>
          <TextField label="Racket Model" name="racket_description" value={state.racket} onChange={text('racket')} placeholder="e.g. Astrox 88D Pro" error={errors.racket_description} maxLength={150} required />
          <TextField label="String Model" name="string_type" value={state.stringModel} onChange={text('stringModel')} placeholder="e.g. BG80" error={errors.string_type} maxLength={150} required />
          <TextField label="String Color" name="string_color" value={state.stringColor} onChange={text('stringColor')} placeholder="Color" error={errors.string_color} maxLength={50} />
          <TextField label="Tension (lbs)" name="tension" value={state.tension} onChange={text('tension')} placeholder="e.g. 26 lbs" error={errors.tension} maxLength={50} />
          <div className="ar-form-grid__wide ar-stringing-form__checks">
            <CheckboxField name="has_stencil" label="Add Stencil" checked={state.hasStencil} onChange={(checked) => dispatch({ type: 'toggle', field: 'hasStencil', checked })} />
            <CheckboxField name="has_grip" label="Add Grip" checked={state.hasGrip} onChange={(checked) => dispatch({ type: 'toggle', field: 'hasGrip', checked })} />
            <CheckboxField
              name="string_from_store"
              label={`String bought from store (-${formatMoney(config.stringingDefaults.storeStringDiscount, { decimals: 0 })})`}
              checked={state.stringFromStore}
              onChange={(checked) => dispatch({ type: 'toggle', field: 'stringFromStore', checked })}
            />
          </div>
          <MoneyField label="Stringing Service" name="service_price" value={state.servicePrice} onChange={text('servicePrice')} error={errors.service_price} required />
          <MoneyField
            label={state.stringFromStore ? 'Store-string Discount' : 'Discount'}
            name="discount_amount"
            value={state.discount}
            onChange={text('discount')}
            error={errors.discount_amount}
            hint={state.stringFromStore ? discountHint : undefined}
          />
          {state.hasStencil && <MoneyField label="Stencil Price" name="stencil_price" value={state.stencilPrice} onChange={text('stencilPrice')} error={errors.stencil_price} required />}
          {state.hasGrip && <MoneyField label="Grip Price" name="grip_price" value={state.gripPrice} onChange={text('gripPrice')} error={errors.grip_price} required />}
          <TextAreaField label="Notes" name="notes" value={state.notes} onChange={text('notes')} rows={2} className="ar-form-grid__wide" />
        </div>
        {!order && (
          <div className="mt-3">
            <Banner>A unique order ID is assigned when the order is created. Status starts as Received.</Banner>
          </div>
        )}
      </Card>

      <Card title="Invoice" className="ar-stringing-form__invoice">
        <div className="d-grid gap-3">
          <InvoiceLines totals={totals} stringFromStore={state.stringFromStore} hasStencil={state.hasStencil} hasGrip={state.hasGrip} />
          {withDeposit && (
            <>
              <MoneyField label="Deposit / payment received" name="deposit" value={state.depositAmount} onChange={text('depositAmount')} placeholder="0.00" error={errors.deposit} />
              <SelectField
                label="Payment Method"
                name="payment_method"
                value={state.depositMethod}
                onChange={(value) => dispatch({ type: 'setDepositMethod', value: value as OrderFormState['depositMethod'] })}
                options={PAYMENT_METHODS}
                placeholder="Select method"
                error={errors['deposit.payment_method']}
              />
              {state.depositMethod && state.depositMethod !== 'CASH' && (
                <TextField label="Reference #" name="reference_number" value={state.depositReference} onChange={text('depositReference')} error={errors['deposit.reference_number']} maxLength={100} />
              )}
            </>
          )}
          {!order && !withDeposit && <Banner tone="info">You can't record payments. The deposit can be collected later from the order's details.</Banner>}
          {!order && (
            <div className="ar-invoice__balance">
              <span>Balance due</span>
              <span>{formatMoney(totals.balance)}</span>
            </div>
          )}
          {alert && (
            <div className="alert alert-danger ar-alert mb-0" role="alert">
              {alert}
            </div>
          )}
          <div className="ar-stringing-form__actions">
            <Button variant="secondary" onClick={() => navigate(back)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button busy={save.isPending} onClick={submit}>
              {order ? 'Save changes' : 'Create order'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

/** Edit an existing order (/stringing/:id/edit); final orders are read only. */
function EditOrder({ id }: { id: number }) {
  const order = useStringingOrder(id)
  return (
    <QueryState isPending={order.isPending} error={order.error}>
      {order.data &&
        (isOpen(order.data.status) ? (
          <OrderForm key={order.data.id} order={order.data} />
        ) : (
          <Card className="ar-page ar-form-card">
            <p>
              Order {order.data.order_number} is {order.data.status_display} and can no longer be edited.
            </p>
            <Link to={`/stringing?order=${order.data.id}`}>Back to the order</Link>
          </Card>
        ))}
    </QueryState>
  )
}

/** /stringing/new (Create a Stringing Order) and /stringing/:id/edit. */
export function StringingOrderFormPage() {
  const { id } = useParams()
  return id ? <EditOrder id={Number(id)} /> : <OrderForm />
}
