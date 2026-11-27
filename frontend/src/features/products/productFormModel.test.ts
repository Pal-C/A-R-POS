import { makeProductDetail } from '../../test/fixtures'
import { diffProduct, emptyProductForm, formFromProduct, toCreatePayload, validateProductForm } from './productFormModel'

describe('validateProductForm', () => {
  it('requires the core fields', () => {
    const errors = validateProductForm({ ...emptyProductForm, stock_quantity: '', low_stock_threshold: '-1' }, { mode: 'add', canViewCost: true })
    expect(Object.keys(errors).sort()).toEqual(
      ['category', 'cost_price', 'low_stock_threshold', 'name', 'selling_price', 'sku', 'stock_quantity'].sort(),
    )
  })

  it('skips cost without the permission and requires a reason when editing', () => {
    const values = { ...emptyProductForm, name: 'X', category: 'RACKET', sku: 'S', selling_price: '1' }
    expect(validateProductForm(values, { mode: 'add', canViewCost: false })).toEqual({})
    expect(validateProductForm(values, { mode: 'edit', canViewCost: false })).toHaveProperty('reason')
  })
})

describe('toCreatePayload', () => {
  it('converts strings to API values and sends stock as initial_stock', () => {
    const payload = toCreatePayload(
      {
        ...emptyProductForm,
        name: ' BG66 ',
        category: 'ACCESSORIES',
        sku: 'YNX',
        selling_price: '₱450',
        cost_price: '320.5',
        stock_quantity: '89',
      },
      true,
    )
    expect(payload).toMatchObject({
      name: 'BG66',
      selling_price: '450.00',
      cost_price: '320.50',
      initial_stock: 89,
      low_stock_threshold: 5,
      is_active: true,
    })
    expect(payload).not.toHaveProperty('stock_quantity')
  })

  it('leaves cost out without the permission', () => {
    expect(toCreatePayload({ ...emptyProductForm, cost_price: '10' }, false)).not.toHaveProperty('cost_price')
  })
})

describe('diffProduct', () => {
  const initial = formFromProduct(makeProductDetail({ selling_price: '450.00', stock_quantity: 89, cost_price: '320.00' }))

  it('returns only changed fields with their original values', () => {
    const { changes, expected } = diffProduct(
      initial,
      { ...initial, selling_price: '480', stock_quantity: '85', reason: 'x' },
      { canViewCost: true, canAdjustStock: true },
    )
    expect(changes).toEqual({ selling_price: '480.00', stock_quantity: 85 })
    expect(expected).toEqual({ selling_price: '450.00', stock_quantity: 89 })
  })

  it('is empty when nothing changed (formatting differences ignored)', () => {
    const { changes } = diffProduct(initial, { ...initial, selling_price: '450', name: ` ${initial.name} ` }, { canViewCost: true, canAdjustStock: true })
    expect(changes).toEqual({})
  })

  it('never sends the active state (activation uses Remove/Reactivate)', () => {
    const { changes } = diffProduct(initial, { ...initial, is_active: false }, { canViewCost: true, canAdjustStock: true })
    expect(changes).toEqual({})
  })

  it('never sends stock or cost without the matching permission', () => {
    const { changes } = diffProduct(
      initial,
      { ...initial, stock_quantity: '1', cost_price: '1' },
      { canViewCost: false, canAdjustStock: false },
    )
    expect(changes).toEqual({})
  })
})
