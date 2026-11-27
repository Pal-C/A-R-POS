import type { Product } from '../../api/catalog'
import type { Money, PaymentMethod } from '../../api/common'
import type { CustomerListItem } from '../../api/customers'
import type { Sale } from '../../api/sales'
import type { FieldErrors } from '../../api/errors'
import { addMoney, compareMoney, multiplyMoney, subtractMoney, sumMoney, toCents } from '../../lib/money'
import { parseMoneyInput } from '../../lib/format'

/** A cart line; `available` caps the quantity (data-model.md CartState). */
export interface CartLine {
  productId: number
  name: string
  type: string
  unitPrice: Money
  quantity: number
  available: number
  /** Line discount carried over from a saved draft (the UI doesn't edit it). */
  discount: Money
}

/** Current catalog data for a draft's products, used when reopening it. */
export interface CurrentProduct {
  selling_price: Money
  stock_quantity: number
  is_active: boolean
}

export interface CartCustomer {
  id: number
  full_name: string
  phone_number: string
}

export interface CartState {
  lines: CartLine[]
  /** Raw input; validated with parseMoneyInput. */
  discount: string
  customer: CartCustomer | null
  paymentMethod: PaymentMethod | ''
  amountPaid: string
  saleDate: string
  backdateReason: string
  clientTransactionId: string
  draftId: number | null
}

export type CartAction =
  | { type: 'add'; product: Pick<Product, 'id' | 'name' | 'selling_price' | 'stock_quantity'> & { typeLabel: string } }
  | { type: 'setQuantity'; productId: number; quantity: number }
  | { type: 'remove'; productId: number }
  | { type: 'setDiscount'; value: string }
  | { type: 'setCustomer'; customer: CartCustomer | CustomerListItem | null }
  | { type: 'setPaymentMethod'; value: PaymentMethod | '' }
  | { type: 'setAmountPaid'; value: string }
  | { type: 'setSaleDate'; value: string }
  | { type: 'setBackdateReason'; value: string }
  | { type: 'loadDraft'; sale: Sale; customer: CartCustomer | null; current: Record<number, CurrentProduct> }
  | { type: 'reset'; today: string }

export function newTransactionId(): string {
  return globalThis.crypto.randomUUID()
}

export function initialCart(today: string): CartState {
  return {
    lines: [],
    discount: '',
    customer: null,
    paymentMethod: '',
    amountPaid: '',
    saleDate: today,
    backdateReason: '',
    clientTransactionId: newTransactionId(),
    draftId: null,
  }
}

const clamp = (n: number, max: number) => Math.max(1, Math.min(n, Math.max(max, 1)))

export function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'add': {
      const { product } = action
      const existing = state.lines.find((l) => l.productId === product.id)
      if (existing) {
        if (existing.quantity >= existing.available) return state
        return {
          ...state,
          lines: state.lines.map((l) => (l.productId === product.id ? { ...l, quantity: l.quantity + 1 } : l)),
        }
      }
      if (product.stock_quantity < 1) return state
      return {
        ...state,
        lines: [
          ...state.lines,
          {
            productId: product.id,
            name: product.name,
            type: product.typeLabel,
            unitPrice: product.selling_price,
            quantity: 1,
            available: product.stock_quantity,
            discount: '0.00',
          },
        ],
      }
    }
    case 'setQuantity':
      return {
        ...state,
        lines: state.lines.map((l) =>
          l.productId === action.productId ? { ...l, quantity: clamp(Math.trunc(action.quantity) || 1, l.available) } : l,
        ),
      }
    case 'remove':
      return { ...state, lines: state.lines.filter((l) => l.productId !== action.productId) }
    case 'setDiscount':
      return { ...state, discount: action.value }
    case 'setCustomer':
      return {
        ...state,
        customer: action.customer
          ? { id: action.customer.id, full_name: action.customer.full_name, phone_number: action.customer.phone_number }
          : null,
      }
    case 'setPaymentMethod':
      return { ...state, paymentMethod: action.value }
    case 'setAmountPaid':
      return { ...state, amountPaid: action.value }
    case 'setSaleDate':
      return { ...state, saleDate: action.value }
    case 'setBackdateReason':
      return { ...state, backdateReason: action.value }
    case 'loadDraft':
      return {
        ...state,
        draftId: action.sale.id,
        customer: action.customer,
        discount: Number(action.sale.discount_amount) ? action.sale.discount_amount : '',
        // Drafts don't hold stock: use current stock and price (what checkout charges).
        lines: action.sale.items.map((item) => {
          const current = action.current[item.product]
          return {
            productId: item.product,
            name: item.product_name,
            type: '',
            unitPrice: current?.selling_price ?? item.unit_selling_price,
            quantity: item.quantity,
            available: current && !current.is_active ? 0 : (current?.stock_quantity ?? item.quantity),
            discount: item.discount_amount,
          }
        }),
      }
    case 'reset':
      return initialCart(action.today)
  }
}

export interface CartTotals {
  subtotal: Money
  discount: Money
  total: Money
  paid: Money
  balance: Money
}

/** Derived totals as Money strings (no floating point). Invalid inputs count as 0. */
const floorAtZero = (amount: Money): Money => (toCents(amount) < 0n ? '0.00' : amount)

/** Sum of line discounts (carried over from drafts). */
export function lineDiscounts(state: CartState): Money {
  return sumMoney(state.lines.map((l) => l.discount))
}

export function cartTotals(state: CartState): CartTotals {
  const subtotal = sumMoney(state.lines.map((l) => multiplyMoney(l.unitPrice, l.quantity)))
  const saleDiscount = parseMoneyInput(state.discount || '0') ?? '0.00'
  const discount = addMoney(lineDiscounts(state), saleDiscount)
  const total = floorAtZero(subtractMoney(subtotal, discount))
  const paid = parseMoneyInput(state.amountPaid || '0') ?? '0.00'
  return { subtotal, discount, total, paid, balance: floorAtZero(subtractMoney(total, paid)) }
}

/** Client checks mirroring the server (data-model.md "Validation"). */
export function validateCart(state: CartState, { today, canBackdate }: { today: string; canBackdate: boolean }): FieldErrors {
  const errors: FieldErrors = {}
  if (state.lines.length === 0) errors.items = ['Add at least one product.']
  const subtotal = subtractMoney(sumMoney(state.lines.map((l) => multiplyMoney(l.unitPrice, l.quantity))), lineDiscounts(state))
  if (state.lines.some((l) => l.available < 1)) errors.items = ['Remove products that are no longer sold.']
  if (state.discount) {
    const discount = parseMoneyInput(state.discount)
    if (discount === null) errors.discount_amount = ['Enter a discount like 40 or 40.00.']
    else if (compareMoney(discount, subtotal) > 0) errors.discount_amount = ["The discount can't be more than the subtotal."]
  }
  if (state.amountPaid || state.paymentMethod) {
    const paid = parseMoneyInput(state.amountPaid)
    if (!state.paymentMethod) errors.payment_method = ['Choose how the customer paid.']
    if (paid === null || toCents(paid) <= 0n) errors.amount_paid = ['Enter the amount paid, more than 0.']
    else if (!errors.discount_amount && compareMoney(paid, cartTotals(state).total) > 0)
      errors.amount_paid = ["Amount paid can't be more than the total. Enter only the amount kept."]
  }
  if (state.saleDate > today) errors.sale_date = ["The date of sale can't be in the future."]
  if (state.saleDate < today) {
    if (!canBackdate) errors.sale_date = ["You can't record a sale with a past date."]
    else if (!state.backdateReason.trim()) errors.backdate_reason = ['Explain why this sale has a past date.']
  }
  return errors
}
