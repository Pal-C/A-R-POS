import { addMoney, compareMoney, fromCents, isZero, multiplyMoney, subtractMoney, sumMoney, toCents } from './money'

describe('money (string amounts, integer cents)', () => {
  it('round-trips through cents', () => {
    expect(toCents('450')).toBe(45000n)
    expect(toCents('450.5')).toBe(45050n)
    expect(toCents('0.05')).toBe(5n)
    expect(toCents('-40.00')).toBe(-4000n)
    expect(fromCents(45050n)).toBe('450.50')
    expect(fromCents(-5n)).toBe('-0.05')
    expect(fromCents(0n)).toBe('0.00')
  })

  it('adds without floating point error', () => {
    expect(addMoney('0.10', '0.20')).toBe('0.30')
    expect(sumMoney(['450.00', '240.00', '0.01'])).toBe('690.01')
    expect(sumMoney([])).toBe('0.00')
  })

  it('subtracts and multiplies', () => {
    expect(subtractMoney('690.00', '40.00')).toBe('650.00')
    expect(subtractMoney('10.00', '12.50')).toBe('-2.50')
    expect(multiplyMoney('120.00', 2)).toBe('240.00')
    expect(multiplyMoney('0.10', 3)).toBe('0.30')
  })

  it('handles large amounts exactly', () => {
    expect(addMoney('99999999999.99', '0.01')).toBe('100000000000.00')
  })

  it('compares', () => {
    expect(compareMoney('650.00', '650')).toBe(0)
    expect(compareMoney('650.01', '650')).toBe(1)
    expect(compareMoney('1', '2')).toBe(-1)
    expect(isZero('0.00')).toBe(true)
  })

  it('rejects invalid input', () => {
    expect(() => toCents('abc')).toThrow()
    expect(() => toCents('1.234')).toThrow()
  })
})
