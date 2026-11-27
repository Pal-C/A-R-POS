import { badgeFor } from './statusBadges'

describe('badgeFor', () => {
  it.each([
    ['stock', 'IN_STOCK', 'In Stock', 'outline'],
    ['stock', 'LOW_STOCK', 'Low Stock', 'yellow'],
    ['stock', 'OUT_OF_STOCK', 'Out of Stock', 'black'],
    ['product', 'active', 'Active', 'navy'],
    ['product', 'inactive', 'Inactive', 'muted'],
    ['sale', 'DRAFT', 'Draft', 'outline'],
    ['sale', 'PENDING_PAYMENT', 'Pending Payment', 'yellow'],
    ['sale', 'COMPLETED', 'Completed', 'navy'],
    ['sale', 'CANCELLED', 'Cancelled', 'black'],
    ['stringing', 'RECEIVED', 'Received', 'outline'],
    ['stringing', 'IN_PROGRESS', 'In Progress', 'sky'],
    ['stringing', 'READY', 'Ready for Pickup', 'yellow'],
    ['stringing', 'COMPLETED', 'Completed', 'navy'],
    ['stringing', 'CANCELLED', 'Cancelled', 'black'],
    ['preorder', 'PENDING', 'Pending', 'outline'],
    ['preorder', 'ORDERED', 'Ordered from Supplier', 'sky'],
    ['preorder', 'ARRIVED', 'Arrived', 'yellow'],
    ['preorder', 'FULFILLED', 'Fulfilled', 'navy'],
    ['preorder', 'CANCELLED', 'Cancelled', 'black'],
  ] as const)('%s %s -> %s (%s)', (domain, value, label, tone) => {
    expect(badgeFor(domain, value)).toEqual({ label, tone })
  })

  it('falls back to a muted badge showing the raw value', () => {
    expect(badgeFor('sale', 'SOMETHING_NEW')).toEqual({ label: 'SOMETHING_NEW', tone: 'muted' })
  })
})
