import type { Money } from '../api/client'

/** Store-local time zone for display; storage stays UTC (constitution). */
export const STORE_TIME_ZONE = import.meta.env.VITE_STORE_TIME_ZONE || 'Asia/Manila'

const moneyFormatters = {
  0: new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP', minimumFractionDigits: 0, maximumFractionDigits: 0 }),
  2: new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP', minimumFractionDigits: 2, maximumFractionDigits: 2 }),
}
const countFormatter = new Intl.NumberFormat('en-PH')
const dateFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: STORE_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})
const timeFormatter = new Intl.DateTimeFormat('en-US', { timeZone: STORE_TIME_ZONE, hour: 'numeric', minute: '2-digit' })

/** Formats a peso amount for display. Display-only: never use the result for arithmetic. */
export function formatMoney(value: Money | number | null | undefined, { decimals = 2 }: { decimals?: 0 | 2 } = {}): string {
  if (value === null || value === undefined || value === '') return '—'
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) return '—'
  return moneyFormatters[decimals].format(amount).replace(/^-?(\s*)/, amount < 0 ? '-' : '')
}

export function formatCount(value: number): string {
  return countFormatter.format(value)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return dateFormatter.format(new Date(iso))
}

/** A business date "YYYY-MM-DD" (no time zone involved) as MM/DD/YYYY. */
export function formatDateOnly(value: string | null | undefined): string {
  const match = value ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(value) : null
  return match ? `${match[2]}/${match[3]}/${match[1]}` : '—'
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return `${dateFormatter.format(date)}, ${timeFormatter.format(date)}`
}

/** Parses a typed amount ("₱1,200.5") into a 2-decimal Money string, or null if invalid. */
export function parseMoneyInput(raw: string): Money | null {
  const cleaned = raw.replace(/[₱,\s]/g, '')
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null
  const [whole, fraction = ''] = cleaned.split('.')
  return `${String(Number(whole))}.${fraction.padEnd(2, '0')}`
}

/** "Maria Reyes" -> "MR"; first and last word initials. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  const first = words[0]!.charAt(0)
  const last = words.length > 1 ? words[words.length - 1]!.charAt(0) : ''
  return `${first}${last}`.toUpperCase()
}

/** Today's business date (YYYY-MM-DD) in the store's time zone. */
export function todayInStore(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: STORE_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
}
