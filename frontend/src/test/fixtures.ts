import type { Product, ProductDetail } from '../api/catalog'
import type { Paginated } from '../api/client'

let nextId = 1

export function makeProduct(overrides: Partial<Product> = {}): Product {
  const id = overrides.id ?? nextId++
  return {
    id,
    sku: `SKU-${id}`,
    name: `Product ${id}`,
    category: 'ACCESSORIES',
    subcategory: 'String',
    brand: 'Yonex',
    variant_description: '',
    model: '',
    supplier: '',
    description: '',
    selling_price: '450.00',
    cost_price: '320.00',
    stock_quantity: 89,
    low_stock_threshold: 5,
    is_low_stock: false,
    is_out_of_stock: false,
    stock_status: 'IN_STOCK',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-18T08:10:00Z',
    ...overrides,
  }
}

export function makeProductDetail(overrides: Partial<ProductDetail> = {}): ProductDetail {
  return {
    ...makeProduct(overrides),
    last_event: {
      action: 'UPDATED',
      performed_by: { id: 3, username: 'maria', display_name: 'Maria Reyes' },
      created_at: '2026-11-18T08:10:00Z',
    },
    ...overrides,
  }
}

export function page<T>(results: T[], count = results.length): Paginated<T> {
  return { count, next: null, previous: null, results }
}

let nextSaleId = 100

export function makeSale(overrides: Partial<import('../api/sales').Sale> = {}): import('../api/sales').Sale {
  const id = overrides.id ?? nextSaleId++
  return {
    id,
    sale_number: `S20261127-${String(id).padStart(6, '0')}`,
    customer: 12,
    customer_name: 'Juan Dela Cruz',
    created_by: 1,
    created_by_name: 'maria',
    subtotal: '690.00',
    item_discount_total: '0.00',
    discount_amount: '40.00',
    total_amount: '650.00',
    amount_paid: '650.00',
    balance: '0.00',
    refund_due: '0.00',
    status: 'COMPLETED',
    created_at: '2026-11-27T08:32:00Z',
    finalized_at: '2026-11-27T08:32:00Z',
    cancelled_at: null,
    sale_date: '2026-11-27',
    items_summary: 'BG66 Ultimax ×1, Super Grap ×2',
    payment_methods: ['CASH'],
    items: [
      { id: 1, product: 7, product_name: 'BG66 Ultimax', product_sku: 'YNX-BG66', quantity: 1, unit_selling_price: '450.00', discount_amount: '0.00', line_subtotal: '450.00', line_total: '450.00', created_at: '2026-11-27T08:32:00Z' },
      { id: 2, product: 9, product_name: 'Super Grap', product_sku: 'YNX-SG', quantity: 2, unit_selling_price: '120.00', discount_amount: '0.00', line_subtotal: '240.00', line_total: '240.00', created_at: '2026-11-27T08:32:00Z' },
    ],
    payments: [
      { id: 1, sale: id, stringing_order: null, preorder: null, amount: '650.00', payment_method: 'CASH', payment_type: 'RECEIPT', status: 'POSTED', payment_date: '2026-11-27T08:32:00Z', reference_number: '', notes: '', received_by: 1, received_by_name: 'maria', created_at: '2026-11-27T08:32:00Z' },
    ],
    cancellation_reason: '',
    cancelled_by: null,
    updated_at: '2026-11-27T08:32:00Z',
    events: [],
    ...overrides,
  }
}

export function makeStringingOrder(overrides: Partial<import('../api/stringing').StringingOrder> = {}): import('../api/stringing').StringingOrder {
  const id = overrides.id ?? 126
  return {
    id,
    order_number: `STR-2026-${String(id).padStart(6, '0')}`,
    customer: { id: 12, full_name: 'Juan Dela Cruz', phone_number: '0917 555 0123', is_active: true },
    racket_description: 'Arcsaber 11',
    string_type: 'BG80',
    string_color: '',
    tension: '27 lbs',
    service_price: '350.00',
    string_from_store: false,
    has_stencil: false,
    stencil_price: '0.00',
    has_grip: false,
    grip_price: '0.00',
    add_ons_total: '0.00',
    discount_amount: '0.00',
    total_amount: '350.00',
    amount_paid: '0.00',
    balance: '350.00',
    refund_due: '0.00',
    payment_state: 'UNPAID',
    status: 'RECEIVED',
    status_display: 'Received',
    created_by: { id: 1, username: 'maria' },
    created_at: '2026-11-19T02:00:00Z',
    updated_at: '2026-11-19T02:00:00Z',
    ready_at: null,
    completed_at: null,
    paid_in_full_at: null,
    cancelled_at: null,
    cancelled_by: null,
    cancellation_reason: '',
    materials_used: null,
    notes: '',
    ...overrides,
  }
}
