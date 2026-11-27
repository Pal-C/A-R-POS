import type { Money } from '../api/client'

/**
 * Exact peso arithmetic on Money strings via integer cents (BigInt), so the
 * cart never uses floating point (specs/006 R7). The server's totals win.
 */
export function toCents(value: Money): bigint {
  const match = /^(-)?(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim())
  if (!match) throw new Error(`Invalid amount: ${value}`)
  const [, sign, whole, fraction = ''] = match
  const cents = BigInt(whole!) * 100n + BigInt(fraction.padEnd(2, '0'))
  return sign ? -cents : cents
}

export function fromCents(cents: bigint): Money {
  const negative = cents < 0n
  const abs = negative ? -cents : cents
  const whole = abs / 100n
  const fraction = (abs % 100n).toString().padStart(2, '0')
  return `${negative ? '-' : ''}${whole}.${fraction}`
}

export const addMoney = (a: Money, b: Money): Money => fromCents(toCents(a) + toCents(b))
export const subtractMoney = (a: Money, b: Money): Money => fromCents(toCents(a) - toCents(b))
export const multiplyMoney = (amount: Money, quantity: number): Money => fromCents(toCents(amount) * BigInt(quantity))
export const sumMoney = (amounts: Money[]): Money => fromCents(amounts.reduce((total, a) => total + toCents(a), 0n))

/** -1, 0 or 1. */
export function compareMoney(a: Money, b: Money): -1 | 0 | 1 {
  const diff = toCents(a) - toCents(b)
  return diff < 0n ? -1 : diff > 0n ? 1 : 0
}

export const isZero = (a: Money): boolean => toCents(a) === 0n
