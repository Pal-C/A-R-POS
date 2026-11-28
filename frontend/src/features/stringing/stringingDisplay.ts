import type { StringingOrderListItem, StringingStatus } from '../../api/stringing'

type OpenStatus = Exclude<StringingStatus, 'COMPLETED' | 'CANCELLED'>

/**
 * Status moves the backend allows, one step at a time (mirrors
 * stringing.services.ALLOWED_TRANSITIONS; specs/007 R6). Final statuses have none.
 */
export const ALLOWED_MOVES: Record<StringingStatus, Exclude<StringingStatus, 'CANCELLED'>[]> = {
  RECEIVED: ['IN_PROGRESS'],
  IN_PROGRESS: ['READY', 'RECEIVED'],
  READY: ['COMPLETED', 'IN_PROGRESS'],
  COMPLETED: [],
  CANCELLED: [],
}

/** The stepper in Details; Cancelled shows a banner instead. */
export const STEPS: StringingStatus[] = ['RECEIVED', 'IN_PROGRESS', 'READY', 'COMPLETED']

export const STATUS_LABELS: Record<StringingStatus, string> = {
  RECEIVED: 'Received',
  IN_PROGRESS: 'In Progress',
  READY: 'Ready for Pickup',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
}

export function isOpen(status: StringingStatus): status is OpenStatus {
  return status !== 'COMPLETED' && status !== 'CANCELLED'
}

type StringFields = Pick<StringingOrderListItem, 'string_type' | 'string_color' | 'string_from_store' | 'tension'>

/** "BG80 · White (store-bought) @ 27 lbs"; the "@" part is left out without a tension. */
export function stringLabel(order: StringFields): string {
  let text = order.string_type
  if (order.string_color) text += ` · ${order.string_color}`
  if (order.string_from_store) text += ' (store-bought)'
  return order.tension ? `${text} @ ${order.tension}` : text
}

/** "Stencil, Grip", or "None". */
export function addOnsLabel(order: Pick<StringingOrderListItem, 'has_stencil' | 'has_grip'>): string {
  const addOns = [order.has_stencil && 'Stencil', order.has_grip && 'Grip'].filter(Boolean)
  return addOns.length ? addOns.join(', ') : 'None'
}

/** "Juan Dela Cruz", or "Walk-in". */
export function customerName(order: Pick<StringingOrderListItem, 'customer'>): string {
  return order.customer?.full_name ?? 'Walk-in'
}

/** The materials answer recorded on a cancellation. */
export function materialsLabel(materialsUsed: boolean | null): string {
  if (materialsUsed === null) return 'Not recorded'
  return materialsUsed ? 'Materials already used' : 'No materials used'
}
