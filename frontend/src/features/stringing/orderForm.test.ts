import type { StringingOrder } from '../../api/stringing'
import { makeStringingOrder } from '../../test/fixtures'
import {
  initialOrderForm,
  orderFormFromOrder,
  createOrderFormReducer,
  orderTotals,
  toCreateBody,
  toUpdateBody,
  validateOrder,
  type OrderFormAction,
  type OrderFormState,
} from './orderForm'

const defaults = { servicePrice: '350.00', stencilPrice: '50.00', gripPrice: '120.00', storeStringDiscount: '100.00' }

const reducer = createOrderFormReducer(defaults)

function apply(state: OrderFormState, ...actions: OrderFormAction[]): OrderFormState {
  return actions.reduce(reducer, state)
}

const filled = (): OrderFormState =>
  apply(
    initialOrderForm(defaults),
    { type: 'set', field: 'racket', value: 'Arcsaber 11' },
    { type: 'set', field: 'stringModel', value: 'BG80' },
  )

describe('orderForm', () => {
  it('starts with the shop service price and no add-ons', () => {
    const state = initialOrderForm(defaults)
    expect(state.servicePrice).toBe('350.00')
    expect(orderTotals(state)).toMatchObject({ total: '350.00', addOns: '0.00', discount: '0.00', balance: '350.00' })
    expect(state.clientTransactionId).toMatch(/[0-9a-f-]{36}/)
  })

  it('pre-fills add-on prices and the store discount when ticked', () => {
    const state = apply(
      filled(),
      { type: 'toggle', field: 'hasStencil', checked: true },
      { type: 'toggle', field: 'hasGrip', checked: true },
      { type: 'toggle', field: 'stringFromStore', checked: true },
    )
    expect(state).toMatchObject({ stencilPrice: '50.00', gripPrice: '120.00', discount: '100.00' })
    expect(orderTotals(state)).toMatchObject({ addOns: '170.00', total: '420.00' })
  })

  it('keeps an overridden price when re-ticking, and drops unticked add-ons from the total', () => {
    let state = apply(filled(), { type: 'toggle', field: 'hasGrip', checked: true }, { type: 'set', field: 'gripPrice', value: '100' })
    state = apply(state, { type: 'toggle', field: 'hasGrip', checked: false })
    expect(orderTotals(state).total).toBe('350.00')
    state = apply(state, { type: 'toggle', field: 'hasGrip', checked: true })
    expect(state.gripPrice).toBe('100')
    expect(orderTotals(state).total).toBe('450.00')
  })

  it('clears only the default store discount when unticked, keeping a typed one', () => {
    let state = apply(filled(), { type: 'toggle', field: 'stringFromStore', checked: true })
    expect(state.discount).toBe('100.00')
    state = apply(state, { type: 'toggle', field: 'stringFromStore', checked: false })
    expect(state.discount).toBe('0.00')
    state = apply(filled(), { type: 'set', field: 'discount', value: '80' }, { type: 'toggle', field: 'stringFromStore', checked: true })
    expect(state.discount).toBe('80')
    state = apply(state, { type: 'toggle', field: 'stringFromStore', checked: false })
    expect(state.discount).toBe('80')
  })

  it('never sends a hidden reference with a cash deposit', () => {
    const state = apply(
      filled(),
      { type: 'set', field: 'depositAmount', value: '100' },
      { type: 'setDepositMethod', value: 'GCASH' },
      { type: 'set', field: 'depositReference', value: 'ABC123' },
      { type: 'setDepositMethod', value: 'CASH' },
    )
    expect(toCreateBody(state, { withDeposit: true }).deposit).toEqual({ amount: '100.00', payment_method: 'CASH', reference_number: '' })
  })

  it('computes the balance after a deposit without floating point', () => {
    const state = apply(filled(), { type: 'set', field: 'servicePrice', value: '0.30' }, { type: 'set', field: 'depositAmount', value: '0.10' })
    expect(orderTotals(state)).toMatchObject({ total: '0.30', deposit: '0.10', balance: '0.20' })
  })

  it('validates required fields, amounts, the discount and the deposit', () => {
    expect(validateOrder(initialOrderForm(defaults), { withDeposit: true })).toEqual({
      racket_description: ['Enter the racket model.'],
      string_type: ['Enter the string model.'],
    })
    const bad = apply(
      filled(),
      { type: 'toggle', field: 'hasStencil', checked: true },
      { type: 'set', field: 'stencilPrice', value: '-5' },
      { type: 'set', field: 'servicePrice', value: 'abc' },
    )
    expect(Object.keys(validateOrder(bad, { withDeposit: false }))).toEqual(['service_price', 'stencil_price'])

    expect(validateOrder(apply(filled(), { type: 'set', field: 'discount', value: '350.01' }), { withDeposit: false })).toEqual({
      discount_amount: ['Discount cannot be more than the service price plus add-ons.'],
    })
    expect(validateOrder(apply(filled(), { type: 'set', field: 'depositAmount', value: '400' }), { withDeposit: true })).toEqual({
      deposit: ['Deposit cannot be more than the total.'],
    })
    expect(validateOrder(apply(filled(), { type: 'set', field: 'depositAmount', value: '100' }), { withDeposit: true })).toEqual({
      'deposit.payment_method': ['Choose how the customer paid.'],
    })
    // Without the payment permission the deposit is ignored.
    expect(validateOrder(apply(filled(), { type: 'set', field: 'depositAmount', value: '400' }), { withDeposit: false })).toEqual({})
  })

  it('builds the create body with the deposit only when there is one', () => {
    const state = apply(
      filled(),
      { type: 'set', field: 'tension', value: ' 27 lbs ' },
      { type: 'toggle', field: 'hasStencil', checked: true },
      { type: 'set', field: 'depositAmount', value: '270' },
      { type: 'setDepositMethod', value: 'GCASH' },
    )
    expect(toCreateBody(state, { withDeposit: true })).toEqual({
      customer: null,
      racket_description: 'Arcsaber 11',
      string_type: 'BG80',
      string_color: '',
      tension: '27 lbs',
      notes: '',
      service_price: '350.00',
      has_stencil: true,
      stencil_price: '50.00',
      has_grip: false,
      grip_price: '0.00',
      string_from_store: false,
      discount_amount: '0.00',
      client_transaction_id: state.clientTransactionId,
      deposit: { amount: '270.00', payment_method: 'GCASH', reference_number: '' },
    })
    expect(toCreateBody(state, { withDeposit: false }).deposit).toBeNull()
  })

  it('sends only changed fields on edit, with add-on flag and price together', () => {
    const order: StringingOrder = makeStringingOrder({ has_stencil: true, stencil_price: '50.00', tension: '26 lbs' })
    const form = orderFormFromOrder(order)
    expect(toUpdateBody(form, order)).toEqual({})
    const edited = apply(form, { type: 'toggle', field: 'hasStencil', checked: false }, { type: 'set', field: 'tension', value: '28 lbs' })
    expect(toUpdateBody(edited, order)).toEqual({ tension: '28 lbs', has_stencil: false, stencil_price: '0.00' })
  })
})
