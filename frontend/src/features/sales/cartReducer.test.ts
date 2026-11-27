import { makeProduct } from '../../test/fixtures'
import { cartReducer, cartTotals, initialCart, validateCart, type CartState } from './cartReducer'

const today = '2026-11-28'
const bg66 = { ...makeProduct({ id: 1, name: 'BG66 Ultimax', selling_price: '450.00', stock_quantity: 2 }), typeLabel: 'String' }
const grip = { ...makeProduct({ id: 2, name: 'Super Grap', selling_price: '120.00', stock_quantity: 56 }), typeLabel: 'Overgrip' }
const soldOut = { ...makeProduct({ id: 3, name: 'Aerosonic', stock_quantity: 0 }), typeLabel: 'String' }

function build(...actions: Parameters<typeof cartReducer>[1][]): CartState {
  return actions.reduce(cartReducer, initialCart(today))
}

describe('cartReducer', () => {
  it('adds products and merges repeated adds, capped at available stock', () => {
    const state = build({ type: 'add', product: bg66 }, { type: 'add', product: bg66 }, { type: 'add', product: bg66 }, { type: 'add', product: grip })
    expect(state.lines.map((l) => [l.name, l.quantity])).toEqual([
      ['BG66 Ultimax', 2],
      ['Super Grap', 1],
    ])
  })

  it('ignores products with no stock', () => {
    expect(build({ type: 'add', product: soldOut }).lines).toEqual([])
  })

  it('bounds quantity between 1 and available', () => {
    const base = build({ type: 'add', product: grip })
    expect(cartReducer(base, { type: 'setQuantity', productId: 2, quantity: 99 }).lines[0]!.quantity).toBe(56)
    expect(cartReducer(base, { type: 'setQuantity', productId: 2, quantity: 0 }).lines[0]!.quantity).toBe(1)
    expect(cartReducer(base, { type: 'setQuantity', productId: 2, quantity: 3.7 }).lines[0]!.quantity).toBe(3)
  })

  it('removes lines', () => {
    const state = build({ type: 'add', product: grip }, { type: 'remove', productId: 2 })
    expect(state.lines).toEqual([])
  })

  it('reset clears the cart with a new transaction id', () => {
    const before = build({ type: 'add', product: grip })
    const after = cartReducer(before, { type: 'reset', today })
    expect(after.lines).toEqual([])
    expect(after.clientTransactionId).not.toBe(before.clientTransactionId)
  })

  it('loads a draft with current stock and prices, keeping line discounts', () => {
    const state = cartReducer(initialCart(today), {
      type: 'loadDraft',
      customer: { id: 9, full_name: 'Juan', phone_number: '0917' },
      current: { 1: { selling_price: '480.00', stock_quantity: 10, is_active: true } },
      sale: {
        id: 42,
        discount_amount: '40.00',
        items: [{ product: 1, product_name: 'BG66 Ultimax', unit_selling_price: '450.00', quantity: 1, discount_amount: '20.00' }],
      } as never,
    })
    expect(state.draftId).toBe(42)
    expect(state.discount).toBe('40.00')
    expect(state.lines[0]).toMatchObject({ productId: 1, quantity: 1, available: 10, unitPrice: '480.00', discount: '20.00' })
    // Review fix #1: the quantity can now go above the saved amount.
    expect(cartReducer(state, { type: 'setQuantity', productId: 1, quantity: 3 }).lines[0]!.quantity).toBe(3)
  })

  it('marks products that are no longer sold as unavailable', () => {
    const state = cartReducer(initialCart(today), {
      type: 'loadDraft',
      customer: null,
      current: { 1: { selling_price: '450.00', stock_quantity: 10, is_active: false } },
      sale: { id: 42, discount_amount: '0.00', items: [{ product: 1, product_name: 'Old', unit_selling_price: '450.00', quantity: 1, discount_amount: '0.00' }] } as never,
    })
    expect(state.lines[0]!.available).toBe(0)
  })
})

describe('cartTotals', () => {
  it('computes subtotal, discount, total and balance as exact strings', () => {
    const state = build(
      { type: 'add', product: bg66 },
      { type: 'add', product: grip },
      { type: 'setQuantity', productId: 2, quantity: 2 },
      { type: 'setDiscount', value: '40' },
      { type: 'setAmountPaid', value: '300' },
    )
    expect(cartTotals(state)).toEqual({ subtotal: '690.00', discount: '40.00', total: '650.00', paid: '300.00', balance: '350.00' })
  })

  it('includes line discounts and never shows a negative total', () => {
    const withLineDiscount = { ...build({ type: 'add', product: grip }), lines: [{ productId: 2, name: 'Super Grap', type: '', unitPrice: '120.00', quantity: 2, available: 56, discount: '30.00' }] }
    expect(cartTotals(withLineDiscount)).toMatchObject({ subtotal: '240.00', discount: '30.00', total: '210.00' })
    const tooMuch = cartReducer(build({ type: 'add', product: grip }), { type: 'setDiscount', value: '500' })
    expect(cartTotals(tooMuch).total).toBe('0.00')
  })
})

describe('validateCart', () => {
  const opts = { today, canBackdate: false }

  it('requires at least one line', () => {
    expect(validateCart(initialCart(today), opts)).toHaveProperty('items')
  })

  it('checks discount and payment against the totals', () => {
    const base = build({ type: 'add', product: grip })
    expect(validateCart(cartReducer(base, { type: 'setDiscount', value: '121' }), opts)).toHaveProperty('discount_amount')
    expect(validateCart(cartReducer(base, { type: 'setDiscount', value: 'x' }), opts)).toHaveProperty('discount_amount')
    const paid = cartReducer(cartReducer(base, { type: 'setPaymentMethod', value: 'CASH' }), { type: 'setAmountPaid', value: '121' })
    expect(validateCart(paid, opts)).toHaveProperty('amount_paid')
    expect(validateCart(cartReducer(base, { type: 'setAmountPaid', value: '10' }), opts)).toHaveProperty('payment_method')
    const ok = cartReducer(paid, { type: 'setAmountPaid', value: '120' })
    expect(validateCart(ok, opts)).toEqual({})
  })

  it('applies the sale date rules', () => {
    const base = build({ type: 'add', product: grip })
    expect(validateCart(cartReducer(base, { type: 'setSaleDate', value: '2026-11-29' }), opts)).toHaveProperty('sale_date')
    const past = cartReducer(base, { type: 'setSaleDate', value: '2026-11-27' })
    expect(validateCart(past, opts)).toHaveProperty('sale_date')
    expect(validateCart(past, { today, canBackdate: true })).toHaveProperty('backdate_reason')
    expect(validateCart(cartReducer(past, { type: 'setBackdateReason', value: 'Paper receipt' }), { today, canBackdate: true })).toEqual({})
  })
})
