import type { Money } from '../../api/client'
import type { PaymentMethod } from '../../api/common'
import type { FieldErrors } from '../../api/errors'
import type { StringingOrder, StringingOrderCreate, StringingOrderWrite } from '../../api/stringing'
import type { CustomerChoice } from '../../components/CustomerPicker'
import { config } from '../../config'
import { parseMoneyInput } from '../../lib/format'
import { compareMoney, fromCents, toCents } from '../../lib/money'

/** Create/Edit form state (specs/007 data-model.md "Frontend form model"). Money stays as typed. */
export interface OrderFormState {
  customer: CustomerChoice | null
  racket: string
  stringModel: string
  stringColor: string
  tension: string
  notes: string
  servicePrice: string
  hasStencil: boolean
  stencilPrice: string
  hasGrip: boolean
  gripPrice: string
  stringFromStore: boolean
  discount: string
  depositAmount: string
  depositMethod: PaymentMethod | ''
  depositReference: string
  /** New per form and kept across retries, so a repeat never creates a second order. */
  clientTransactionId: string
}

export type OrderDefaults = (typeof config)['stringingDefaults']

export type OrderTextField = Exclude<keyof OrderFormState, 'customer' | 'hasStencil' | 'hasGrip' | 'stringFromStore' | 'depositMethod' | 'clientTransactionId'>

export type OrderFormAction =
  | { type: 'set'; field: OrderTextField; value: string }
  | { type: 'setCustomer'; customer: CustomerChoice | null }
  | { type: 'setDepositMethod'; value: PaymentMethod | '' }
  | { type: 'toggle'; field: 'hasStencil' | 'hasGrip' | 'stringFromStore'; checked: boolean }

export function initialOrderForm(defaults: OrderDefaults = config.stringingDefaults): OrderFormState {
  return {
    customer: null,
    racket: '',
    stringModel: '',
    stringColor: '',
    tension: '',
    notes: '',
    servicePrice: defaults.servicePrice,
    hasStencil: false,
    stencilPrice: '',
    hasGrip: false,
    gripPrice: '',
    stringFromStore: false,
    discount: '0.00',
    depositAmount: '',
    depositMethod: '',
    depositReference: '',
    clientTransactionId: globalThis.crypto.randomUUID(),
  }
}

/** The form for editing an existing order (no deposit). */
export function orderFormFromOrder(order: StringingOrder): OrderFormState {
  return {
    ...initialOrderForm(),
    customer: order.customer ? { id: order.customer.id, full_name: order.customer.full_name, phone_number: order.customer.phone_number } : null,
    racket: order.racket_description,
    stringModel: order.string_type,
    stringColor: order.string_color,
    tension: order.tension,
    notes: order.notes,
    servicePrice: order.service_price,
    hasStencil: order.has_stencil,
    stencilPrice: order.has_stencil ? order.stencil_price : '',
    hasGrip: order.has_grip,
    gripPrice: order.has_grip ? order.grip_price : '',
    stringFromStore: order.string_from_store,
    discount: order.discount_amount,
  }
}

const PRICE_FOR = { hasStencil: 'stencilPrice', hasGrip: 'gripPrice' } as const

/** The form reducer, pre-filling ticked add-ons and the store discount from `defaults`. */
export function createOrderFormReducer(defaults: OrderDefaults) {
  return (state: OrderFormState, action: OrderFormAction): OrderFormState => reduce(state, action, defaults)
}

export const orderFormReducer = createOrderFormReducer(config.stringingDefaults)

function reduce(state: OrderFormState, action: OrderFormAction, defaults: OrderDefaults): OrderFormState {
  switch (action.type) {
    case 'set':
      return { ...state, [action.field]: action.value }
    case 'setCustomer':
      return { ...state, customer: action.customer }
    case 'setDepositMethod':
      return { ...state, depositMethod: action.value }
    case 'toggle': {
      const next = { ...state, [action.field]: action.checked }
      if (action.field === 'stringFromStore') {
        // Ticking fills the shop discount unless one was typed; unticking clears only that
        // default, so a discount staff typed themselves is kept.
        const storeDefault = toCents(parseMoneyInput(defaults.storeStringDiscount) ?? '0')
        if (!action.checked && amountOf(state.discount) === storeDefault) next.discount = '0.00'
        else if (action.checked && amountOf(state.discount) === 0n) next.discount = defaults.storeStringDiscount
        return next
      }
      const priceField = PRICE_FOR[action.field]
      if (action.checked && !state[priceField].trim()) {
        next[priceField] = action.field === 'hasStencil' ? defaults.stencilPrice : defaults.gripPrice
      }
      return next
    }
  }
}

/** Cents for a typed amount; blank or invalid counts as 0 (validation reports it). */
function amountOf(raw: string): bigint {
  const parsed = parseMoneyInput(raw)
  return parsed === null ? 0n : toCents(parsed)
}

export interface OrderTotals {
  service: Money
  stencil: Money
  grip: Money
  addOns: Money
  discount: Money
  total: Money
  deposit: Money
  balance: Money
}

export function orderTotals(state: OrderFormState): OrderTotals {
  const service = amountOf(state.servicePrice)
  const stencil = state.hasStencil ? amountOf(state.stencilPrice) : 0n
  const grip = state.hasGrip ? amountOf(state.gripPrice) : 0n
  const discount = amountOf(state.discount)
  const total = service + stencil + grip - discount
  const deposit = amountOf(state.depositAmount)
  return {
    service: fromCents(service),
    stencil: fromCents(stencil),
    grip: fromCents(grip),
    addOns: fromCents(stencil + grip),
    discount: fromCents(discount),
    total: fromCents(total),
    deposit: fromCents(deposit),
    balance: fromCents(total - deposit),
  }
}

/** Field errors keyed by API field names, so server errors land on the same fields. */
export function validateOrder(state: OrderFormState, { withDeposit }: { withDeposit: boolean }): FieldErrors {
  const errors: FieldErrors = {}
  if (!state.racket.trim()) errors.racket_description = ['Enter the racket model.']
  if (!state.stringModel.trim()) errors.string_type = ['Enter the string model.']

  const money: [string, string, boolean][] = [
    ['service_price', state.servicePrice, true],
    ['stencil_price', state.stencilPrice, state.hasStencil],
    ['grip_price', state.gripPrice, state.hasGrip],
    ['discount_amount', state.discount || '0', true],
  ]
  for (const [field, raw, used] of money) {
    if (used && parseMoneyInput(raw) === null) errors[field] = ['Enter an amount of 0 or more, e.g. 120.00.']
  }

  const totals = orderTotals(state)
  if (!errors.discount_amount && compareMoney(totals.total, '0.00') < 0) {
    errors.discount_amount = ['Discount cannot be more than the service price plus add-ons.']
  }

  if (withDeposit && state.depositAmount.trim()) {
    const deposit = parseMoneyInput(state.depositAmount)
    if (deposit === null) errors.deposit = ['Enter an amount, e.g. 200.00.']
    else if (compareMoney(deposit, totals.total) > 0) errors.deposit = ['Deposit cannot be more than the total.']
    else if (toCents(deposit) > 0n && !state.depositMethod) errors['deposit.payment_method'] = ['Choose how the customer paid.']
  }
  return errors
}

function writeBody(state: OrderFormState): Required<Omit<StringingOrderWrite, 'direct_cost'>> {
  const money = (raw: string) => parseMoneyInput(raw || '0') ?? '0.00'
  return {
    customer: state.customer?.id ?? null,
    racket_description: state.racket.trim(),
    string_type: state.stringModel.trim(),
    string_color: state.stringColor.trim(),
    tension: state.tension.trim(),
    notes: state.notes.trim(),
    service_price: money(state.servicePrice),
    has_stencil: state.hasStencil,
    stencil_price: state.hasStencil ? money(state.stencilPrice) : '0.00',
    has_grip: state.hasGrip,
    grip_price: state.hasGrip ? money(state.gripPrice) : '0.00',
    string_from_store: state.stringFromStore,
    discount_amount: money(state.discount),
  }
}

export function toCreateBody(state: OrderFormState, { withDeposit }: { withDeposit: boolean }): StringingOrderCreate {
  const deposit = withDeposit ? parseMoneyInput(state.depositAmount) : null
  return {
    ...writeBody(state),
    client_transaction_id: state.clientTransactionId,
    deposit:
      deposit && toCents(deposit) > 0n && state.depositMethod
        ? {
            amount: deposit,
            payment_method: state.depositMethod,
            // The reference field is hidden for cash, so a leftover value is never sent.
            reference_number: state.depositMethod === 'CASH' ? '' : state.depositReference.trim(),
          }
        : null,
  }
}

/** Only the fields that differ from the saved order. Add-on flag and price always travel together. */
export function toUpdateBody(state: OrderFormState, order: StringingOrder): Partial<StringingOrderWrite> {
  const body = writeBody(state)
  const saved: typeof body = {
    customer: order.customer?.id ?? null,
    racket_description: order.racket_description,
    string_type: order.string_type,
    string_color: order.string_color,
    tension: order.tension,
    notes: order.notes,
    service_price: order.service_price,
    has_stencil: order.has_stencil,
    stencil_price: order.stencil_price,
    has_grip: order.has_grip,
    grip_price: order.grip_price,
    string_from_store: order.string_from_store,
    discount_amount: order.discount_amount,
  }
  const changes: Partial<StringingOrderWrite> = {}
  for (const key of Object.keys(body) as (keyof typeof body)[]) {
    if (body[key] !== saved[key]) Object.assign(changes, { [key]: body[key] })
  }
  for (const [flag, price] of [['has_stencil', 'stencil_price'], ['has_grip', 'grip_price']] as const) {
    if (flag in changes || price in changes) Object.assign(changes, { [flag]: body[flag], [price]: body[price] })
  }
  return changes
}

/** Server error keys → the form field that shows them. */
export function formFieldFor(key: string): string | null {
  if (key === 'deposit' || key === 'deposit.amount') return 'deposit'
  if (key.startsWith('deposit.payment_method')) return 'deposit.payment_method'
  if (key.startsWith('deposit.reference_number')) return 'deposit.reference_number'
  const known = ['customer', 'racket_description', 'string_type', 'string_color', 'tension', 'notes', 'service_price', 'stencil_price', 'grip_price', 'discount_amount']
  return known.includes(key) ? key : null
}
