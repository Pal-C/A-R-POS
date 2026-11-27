import { formatCount, formatDate, formatDateTime, formatMoney, initials, parseMoneyInput } from './format'

describe('formatMoney', () => {
  it('formats pesos with two decimals by default', () => {
    expect(formatMoney('650')).toBe('₱650.00')
    expect(formatMoney('186400.5')).toBe('₱186,400.50')
  })

  it('can drop decimals for compact display', () => {
    expect(formatMoney('11500.00', { decimals: 0 })).toBe('₱11,500')
  })

  it('formats negatives and numbers', () => {
    expect(formatMoney('-40')).toBe('-₱40.00')
    expect(formatMoney(0)).toBe('₱0.00')
  })

  it('shows a dash for missing or invalid values', () => {
    expect(formatMoney(undefined)).toBe('—')
    expect(formatMoney('abc')).toBe('—')
  })
})

describe('formatCount', () => {
  it('adds thousands separators', () => {
    expect(formatCount(1234567)).toBe('1,234,567')
  })
})

describe('dates in the store time zone (Asia/Manila)', () => {
  it('uses MM/DD/YYYY and crosses the UTC day boundary correctly', () => {
    // 2026-11-08 20:30 UTC is 2026-11-09 04:30 in Manila.
    expect(formatDate('2026-11-08T20:30:00Z')).toBe('11/09/2026')
  })

  it('formats date and time with AM/PM', () => {
    expect(formatDateTime('2026-11-08T08:32:00Z')).toBe('11/08/2026, 4:32 PM')
  })

  it('shows a dash for missing values', () => {
    expect(formatDate(null)).toBe('—')
  })
})

describe('parseMoneyInput', () => {
  it.each([
    ['1200.5', '1200.50'],
    ['₱1,200.5', '1200.50'],
    [' 450 ', '450.00'],
    ['0', '0.00'],
  ])('parses %s as %s', (raw, expected) => {
    expect(parseMoneyInput(raw)).toBe(expected)
  })

  it.each(['abc', '1.234', '-1', '', '1..2'])('rejects %s', (raw) => {
    expect(parseMoneyInput(raw)).toBeNull()
  })
})

describe('initials', () => {
  it.each([
    ['Maria Reyes', 'MR'],
    ['solo', 'S'],
    ['  juan  dela  cruz ', 'JC'],
    ['', '?'],
  ])('%s -> %s', (name, expected) => {
    expect(initials(name)).toBe(expected)
  })
})
