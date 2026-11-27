/** One status -> label/tone mapping for the whole app (data-model.md StatusBadgeSpec, FR-003). */
export type BadgeTone = 'outline' | 'navy' | 'sky' | 'yellow' | 'black' | 'muted'

export interface StatusBadgeSpec {
  label: string
  tone: BadgeTone
}

export const STATUS_BADGES = {
  stock: {
    IN_STOCK: { label: 'In Stock', tone: 'outline' },
    LOW_STOCK: { label: 'Low Stock', tone: 'yellow' },
    OUT_OF_STOCK: { label: 'Out of Stock', tone: 'black' },
  },
  product: {
    active: { label: 'Active', tone: 'navy' },
    inactive: { label: 'Inactive', tone: 'muted' },
  },
  sale: {
    DRAFT: { label: 'Draft', tone: 'outline' },
    PENDING_PAYMENT: { label: 'Pending Payment', tone: 'yellow' },
    COMPLETED: { label: 'Completed', tone: 'navy' },
    CANCELLED: { label: 'Cancelled', tone: 'black' },
  },
  stringing: {
    RECEIVED: { label: 'Received', tone: 'outline' },
    IN_PROGRESS: { label: 'In Progress', tone: 'sky' },
    READY: { label: 'Ready for Pickup', tone: 'yellow' },
    COMPLETED: { label: 'Completed', tone: 'navy' },
    CANCELLED: { label: 'Cancelled', tone: 'black' },
  },
  preorder: {
    PENDING: { label: 'Pending', tone: 'outline' },
    ORDERED: { label: 'Ordered from Supplier', tone: 'sky' },
    ARRIVED: { label: 'Arrived', tone: 'yellow' },
    FULFILLED: { label: 'Fulfilled', tone: 'navy' },
    CANCELLED: { label: 'Cancelled', tone: 'black' },
  },
} as const satisfies Record<string, Record<string, StatusBadgeSpec>>

export type BadgeDomain = keyof typeof STATUS_BADGES

export function badgeFor(domain: BadgeDomain, value: string): StatusBadgeSpec {
  const specs: Record<string, StatusBadgeSpec> = STATUS_BADGES[domain]
  return specs[value] ?? { label: value, tone: 'muted' }
}
