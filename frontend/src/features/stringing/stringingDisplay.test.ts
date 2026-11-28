import { ALLOWED_MOVES, addOnsLabel, materialsLabel, stringLabel } from './stringingDisplay'

describe('stringingDisplay', () => {
  it('mirrors the backend transitions (stringing.services.ALLOWED_TRANSITIONS)', () => {
    expect(ALLOWED_MOVES).toEqual({
      RECEIVED: ['IN_PROGRESS'],
      IN_PROGRESS: ['READY', 'RECEIVED'],
      READY: ['COMPLETED', 'IN_PROGRESS'],
      COMPLETED: [],
      CANCELLED: [],
    })
  })

  it('labels the string with colour, store-bought and tension', () => {
    const base = { string_type: 'BG80', string_color: '', string_from_store: false, tension: '' }
    expect(stringLabel(base)).toBe('BG80')
    expect(stringLabel({ ...base, tension: '27 lbs' })).toBe('BG80 @ 27 lbs')
    expect(stringLabel({ ...base, string_color: 'White', string_from_store: true, tension: '27 lbs' })).toBe('BG80 · White (store-bought) @ 27 lbs')
  })

  it('labels add-ons and materials', () => {
    expect(addOnsLabel({ has_stencil: false, has_grip: false })).toBe('None')
    expect(addOnsLabel({ has_stencil: true, has_grip: true })).toBe('Stencil, Grip')
    expect(materialsLabel(null)).toBe('Not recorded')
    expect(materialsLabel(true)).toBe('Materials already used')
    expect(materialsLabel(false)).toBe('No materials used')
  })
})
